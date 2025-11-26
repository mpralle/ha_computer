"""Selection Agent: LLM-based selection of specific entities from available options."""
from __future__ import annotations

import json
import logging
from typing import Any

from .llm_client import LlamaCppClient

_LOGGER = logging.getLogger(__name__)

# System prompt for the Selection Agent
SELECTION_SYSTEM_PROMPT = """You select Home Assistant entities from a list.

INPUT: JSON with user's targets and available entities
OUTPUT: JSON with selected entity IDs

RULES:
1. Match target names to friendly_name (ignore case)
2. If target is part of friendly_name, select it
3. You MUST ONLY use entity_id values that appear in the 'available_entities' list.
   Never invent or guess new entity_ids.
4. If no suitable entity matches, return an empty 'selected_entities' list.
5. Output ONLY valid JSON, nothing else
6. Format: {"selected_entities": ["entity.id1", "entity.id2"], "service_data": {"domain": "light", "service": "turn_on", "data": {}}}

EXAMPLES:

Input: {"raw_targets": ["Regallampe"], "available_entities": [{"entity_id": "light.regallampe", "friendly_name": "Regallampe"}, {"entity_id": "light.schranklampe", "friendly_name": "Schranklampe"}]}
Output: {"selected_entities": ["light.regallampe"], "service_data": {"domain": "light", "service": "turn_on", "data": {}}}

Input: {"raw_targets": ["Schrank"], "available_entities": [{"entity_id": "light.schranklampe", "friendly_name": "Schranklampe"}, {"entity_id": "light.schranklicht_innen", "friendly_name": "Schrank Innen"}]}
Output: {"selected_entities": ["light.schranklampe", "light.schranklicht_innen"], "service_data": {"domain": "light", "service": "turn_on", "data": {}}}

ONLY output the JSON object, no explanations or code."""



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
        available_entities = task.get("available_entities", [])
        raw_targets = task.get("raw_targets", [])
        params = task.get("params", {})

        # Build set of valid entity_ids
        available_ids = {
            e.get("entity_id")
            for e in available_entities
            if isinstance(e, dict) and e.get("entity_id")
        }

        selection_input = {
            "raw_targets": raw_targets,
            "available_entities": available_entities,
            "params": params,
        }

        messages = [
            {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(selection_input, ensure_ascii=False)},
        ]

        _LOGGER.debug(
            "Selecting entities for targets %s from %d available: %s",
            raw_targets,
            len(available_entities),
            [e.get("entity_id") for e in available_entities],
        )

        try:
            selection_result = await self.llm_client.parse_json_response(
                messages,
                temperature=0.1,
                max_tokens=300,
                timeout=60,
            )
        except Exception as err:
            _LOGGER.error("Selection Agent failed: %s", err)
            task["selected_entities"] = []
            task["service_data"] = {}
            task["status"] = "failed"
            return task

        # --- Harter Filter auf bekannte Entities ---
        raw_selected = selection_result.get("selected_entities") or []
        filtered_selected = [eid for eid in raw_selected if eid in available_ids]

        if len(filtered_selected) != len(raw_selected):
            _LOGGER.warning(
                "Selection Agent proposed unknown entities %s (valid: %s)",
                [eid for eid in raw_selected if eid not in available_ids],
                list(available_ids),
            )

        selected_entities = filtered_selected

        # --- Fallback: simple String-Matching, falls LLM nichts Nutzbares liefert ---
        if not selected_entities and available_entities and raw_targets:
            _LOGGER.info(
                "No valid entities from LLM, falling back to local name matching for targets %s",
                raw_targets,
            )
            lowered_targets = [t.lower() for t in raw_targets]

            for entity in available_entities:
                friendly = (entity.get("friendly_name") or "").lower()
                eid = entity.get("entity_id")
                if not eid:
                    continue

                if any(t in friendly for t in lowered_targets):
                    selected_entities.append(eid)

            if not selected_entities:
                _LOGGER.warning(
                    "Fallback matching also found no entities for targets %s",
                    raw_targets,
                )


        # --- Build service_data based on TASK's action, not LLM response ---
        # The Selection Agent should ONLY select entities, NOT change the action/service
        action = task.get("action", "turn_on")
        domain = task.get("domain", "light")
        
        # Merge params from task.params AND any task-level fields that look like service parameters
        # (e.g., "temperature", "brightness", "hvac_mode", etc.)
        service_params = dict(params)  # Start with explicit params
        
        # Extract common service parameters that might be at task level
        param_fields = ["temperature", "target_temperature", "temp",  # Temperature variations
                       "hvac_mode", "brightness", "color_temp", "position", 
                       "percentage", "speed", "volume_level", "media_content_id"]
        for field in param_fields:
            if field in task and field not in service_params:
                service_params[field] = task[field]
        
        # Normalize parameters for HA compatibility
        service_params = self._normalize_service_params(service_params, domain)
        
        service_data = {
            "domain": domain,
            "service": self._action_to_service(action, domain),  # Pass domain for proper mapping
            "data": service_params  # Merged and normalized parameters
        }
        
        _LOGGER.debug(
            "Using service from task action '%s' -> service '%s' with params %s (ignoring LLM suggestion)",
            action,
            service_data["service"],
            service_params
        )

        task["selected_entities"] = selected_entities
        task["service_data"] = service_data

        # Status setzen
        if selected_entities:
            task["status"] = "ready_for_execution"
        else:
            # No entities selected - mark as ready but executor will skip it
            task["status"] = "ready_for_execution"

        _LOGGER.info(
            "Selected %d entities (validated) for %s.%s: %s",
            len(selected_entities),
            service_data["domain"],
            service_data["service"],
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


    def _normalize_service_params(self, params: dict[str, Any], domain: str) -> dict[str, Any]:
        """
        Normalize service parameters to match Home Assistant expectations.
        
        Handles:
        - Parameter name variations (target_temperature → temperature)
        - Type conversions (string "25°C" → float 25.0)
        - Domain-specific requirements
        """
        normalized = {}
        
        for key, value in params.items():
            # Normalize parameter names
            if key in ("target_temperature", "temp"):
                key = "temperature"  # HA climate uses "temperature"

            
            # Type conversion based on parameter
            if key == "temperature":
                # Parse temperature strings to float
                if isinstance(value, str):
                    # Remove units like "°C", "°F", "degrees", etc.
                    import re
                    clean = re.sub(r'[°CFcf\s]|degrees?|grad', '', value, flags=re.IGNORECASE)
                    try:
                        value = float(clean)
                    except ValueError:
                        _LOGGER.warning("Could not parse temperature '%s', using as-is", value)
            
            elif key in ("brightness", "color_temp", "percentage", "position"):
                # These should be integers or floats
                if isinstance(value, str):
                    try:
                        value = int(value) if value.isdigit() else float(value)
                    except ValueError:
                        _LOGGER.warning("Could not parse numeric value '%s', using as-is", value)
            
            normalized[key] = value
        
        return normalized
    
    
    def _action_to_service(self, action: str, domain: str = "light") -> str:
        """
        Convert action to service name based on domain.
        
        This mapping ensures the correct service is called for each domain type.
        Supports all major Home Assistant domains.
        """
        action_lower = action.lower()
        
        # Domain-specific action mappings
        if domain == "climate":
            mapping = {
                "set_temperature": "set_temperature",
                "set_temp": "set_temperature",
                "set_hvac_mode": "set_hvac_mode",
                "set_mode": "set_hvac_mode",
                "turn_on": "turn_on",
                "turn_off": "turn_off",
            }
            return mapping.get(action_lower, "set_temperature")
        
        elif domain == "cover":
            mapping = {
                "open": "open_cover",
                "open_cover": "open_cover",
                "close": "close_cover",
                "close_cover": "close_cover",
                "stop": "stop_cover",
                "stop_cover": "stop_cover",
                "toggle": "toggle",
            }
            return mapping.get(action_lower, "toggle")
        
        elif domain == "lock":
            mapping = {
                "lock": "lock",
                "unlock": "unlock",
                "open": "open",
            }
            return mapping.get(action_lower, "lock")
        
        elif domain == "media_player":
            mapping = {
                "play": "media_play",
                "media_play": "media_play",
                "pause": "media_pause",
                "media_pause": "media_pause",
                "stop": "media_stop",
                "media_stop": "media_stop",
                "next": "media_next_track",
                "previous": "media_previous_track",
                "volume_up": "volume_up",
                "volume_down": "volume_down",
                "mute": "volume_mute",
                "turn_on": "turn_on",
                "turn_off": "turn_off",
            }
            return mapping.get(action_lower, "media_play")
        
        elif domain == "fan":
            mapping = {
                "turn_on": "turn_on",
                "turn_off": "turn_off",
                "toggle": "toggle",
                "set_speed": "set_percentage",
                "set_percentage": "set_percentage",
            }
            return mapping.get(action_lower, "turn_on")
        
        elif domain == "vacuum":
            mapping = {
                "start": "start",
                "pause": "pause",
                "stop": "stop",
                "return_to_base": "return_to_base",
                "clean_spot": "clean_spot",
                "turn_on": "start",
                "turn_off": "return_to_base",
            }
            return mapping.get(action_lower, "start")
        
        elif domain in ("light", "switch"):
            # Standard on/off/toggle devices
            mapping = {
                "turn_on": "turn_on",
                "on": "turn_on",
                "turn_off": "turn_off",
                "off": "turn_off",
                "toggle": "toggle",
                "set": "turn_on",  # "set" with params = turn_on
            }
            return mapping.get(action_lower, "turn_on")
        
        else:
            # Default fallback for unknown domains
            mapping = {
                "turn_on": "turn_on",
                "turn_off": "turn_off",
                "toggle": "toggle",
            }
            return mapping.get(action_lower, "turn_on")
