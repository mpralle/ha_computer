"""Selection Agent: LLM-based selection of specific entities from available options."""
from __future__ import annotations

import json
import logging
from typing import Any

from .llm_client import LlamaCppClient

_LOGGER = logging.getLogger(__name__)

# System prompt for the Selection Agent
SELECTION_SYSTEM_PROMPT = """You are an entity selector. Your job is to choose the correct Home Assistant entities from available options.

INPUT:
- User's original targets (what they said)
- List of available entities with friendly_names
- Service schema (what parameters are available)

OUTPUT:
JSON with selected entity_ids

RULES:
1. Match user's target names to friendly_names (case-insensitive, fuzzy)
2. If target matches multiple entities, choose the most specific match
3. If user says multiple targets, select multiple entities
4. Output must be valid JSON: {"selected_entities": ["entity.id1", "entity.id2"], "service_data": {...}}
5. Use the service_schema to build correct service_data
6. NEVER invent entity_ids - only choose from available_entities

EXAMPLES:

Input:
{
  "raw_targets": ["Regallampe", "Schranklampe"],
  "available_entities": [
    {"entity_id": "light.regallampe", "friendly_name": "Regallampe"},
    {"entity_id": "light.schranklampe", "friendly_name": "Schranklampe"},
    {"entity_id": "light.regal_rgb", "friendly_name": "Regal RGB Strip"}
  ],
  "params": {"brightness": 80}
}

Output:
{
  "selected_entities": ["light.regallampe", "light.schranklampe"],
  "service_data": {
    "domain": "light",
    "service": "turn_on",
    "data": {"brightness": 80}
  }
}

Input:
{
  "raw_targets": ["Schrank"],
  "available_entities": [
    {"entity_id": "light.schranklampe", "friendly_name": "Schranklampe"},
    {"entity_id": "light.schranklicht_innen", "friendly_name": "Schrank Innen"}
  ]
}

Output:
{
  "selected_entities": ["light.schranklampe", "light.schranklicht_innen"],
  "service_data": {
    "domain": "light",
    "service": "turn_on",
    "data": {}
  }
}"""


class SelectionAgent:
    """
    Agent that selects specific entities from available options using LLM.
    
    This agent handles the ambiguous cases where semantic understanding is needed
    to match user's intent to specific entities.
    """
    
    def __init__(self, llm_client: LlamaCppClient) -> None:
        """Initialize the Selection Agent."""
        self.llm_client = llm_client
    
    async def select(self, resolved_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Select specific entities for tasks that need selection.
        
        Args:
            resolved_tasks: List of tasks from Resolver with available options
        
        Returns:
            List of concrete tasks with selected entities
        """
        concrete_tasks = []
        
        for task in resolved_tasks:
            if task.get("status") == "awaiting_selection":
                # LLM needed for selection
                task_type = task.get("type")
                
                if task_type == "device_control":
                    selected_task = await self._select_device_entities(task)
                elif task_type == "calendar_create":
                    selected_task = await self._select_calendar(task)
                else:
                    # Unknown task type needing selection, pass through
                    selected_task = task
                    selected_task["status"] = "ready_for_execution"
            else:
                # No selection needed
                selected_task = task
            
            concrete_tasks.append(selected_task)
        
        return concrete_tasks
    
    async def _select_device_entities(self, task: dict[str, Any]) -> dict[str, Any]:
        """Use LLM to select specific device entities."""
        # Build compact selection prompt
        selection_input = {
            "raw_targets": task.get("raw_targets", []),
            "available_entities": task.get("available_entities", []),
            "params": task.get("params", {}),
        }
        
        messages = [
            {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(selection_input, ensure_ascii=False)},
        ]
        
        _LOGGER.debug(
            "Selecting entities for targets %s from %d available",
            task.get("raw_targets"),
            len(task.get("available_entities", [])),
        )
        
        try:
            selection_result = await self.llm_client.parse_json_response(
                messages,
                temperature=0.1,
                max_tokens=300,
                timeout=30,
            )
        except Exception as err:
            _LOGGER.error("Selection Agent failed: %s", err)
            # Fallback: select nothing (will fail in execution)
            task["selected_entities"] = []
            task["service_data"] = {}
            task["status"] = "failed"
            return task
        
        # Validate and update task
        selected_entities = selection_result.get("selected_entities", [])
        service_data = selection_result.get("service_data", {})
        
        if not selected_entities:
            _LOGGER.warning(
                "Selection Agent selected no entities for targets %s",
                task.get("raw_targets"),
            )
        
        # Ensure service_data has domain and service
        if not service_data.get("domain"):
            service_data["domain"] = task.get("domain", "light")
        if not service_data.get("service"):
            action = task.get("action", "turn_on")
            service_data["service"] = self._action_to_service(action)
        
        task["selected_entities"] = selected_entities
        task["service_data"] = service_data
        task["status"] = "ready_for_execution"
        
        _LOGGER.info(
            "Selected %d entities: %s",
            len(selected_entities),
            selected_entities,
        )
        
        return task
    
    async def _select_calendar(self, task: dict[str, Any]) -> dict[str, Any]:
        """Select which calendar to use for event creation."""
        available_calendars = task.get("available_calendars", [])
        
        if not available_calendars:
            # No calendars available
            task["selected_calendar"] = None
            task["status"] = "ready_for_execution"
            return task
        
        if len(available_calendars) == 1:
            # Only one calendar, select it automatically
            task["selected_calendar"] = available_calendars[0]["entity_id"]
            task["status"] = "ready_for_execution"
            _LOGGER.info("Auto-selected single calendar: %s", task["selected_calendar"])
            return task
        
        # Multiple calendars - use LLM to choose (could also default to first)
        # For now, just select the first one
        task["selected_calendar"] = available_calendars[0]["entity_id"]
        task["status"] = "ready_for_execution"
        _LOGGER.info(
            "Selected default calendar: %s from %d available",
            task["selected_calendar"],
            len(available_calendars),
        )
        
        return task
    
    def _action_to_service(self, action: str) -> str:
        """Convert action to service name."""
        if action == "turn_on":
            return "turn_on"
        elif action == "turn_off":
            return "turn_off"
        elif action == "toggle":
            return "toggle"
        elif action == "set":
            return "turn_on"
        else:
            return "turn_on"
