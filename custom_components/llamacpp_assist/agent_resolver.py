"""Resolver Agent: Provides available entities and options for tasks (deterministic logic)."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class TaskResolver:
    """
    Agent that enriches tasks with available options using deterministic logic.
    
    This agent does NOT make selections - it only provides the choices.
    The Selection Agent (LLM) will make the actual decisions.
    """
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Task Resolver."""
        self.hass = hass
    
    async def resolve_tasks(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Provide available options for each task.
        
        Args:
            tasks: List of abstract tasks from Planner
        
        Returns:
            List of tasks with available options added
        """
        resolved = []
        
        for task in tasks:
            task_type = task.get("type")
            
            if task_type == "device_control":
                resolved_task = await self._resolve_device_control(task)
            elif task_type == "shopping_add":
                resolved_task = self._resolve_shopping_add(task)
            elif task_type == "calendar_query":
                resolved_task = self._resolve_calendar_query(task)
            elif task_type == "calendar_create":
                resolved_task = await self._resolve_calendar_create(task)
            else:
                # Pass through for tasks that don't need resolution
                resolved_task = task
                resolved_task["status"] = "ready_for_execution"
            
            resolved.append(resolved_task)
        
        return resolved
    
    async def _resolve_device_control(self, task: dict[str, Any]) -> dict[str, Any]:
        """Provide available entities and service schema for device control."""
        domain = task.get("domain") or self._guess_domain(task.get("raw_targets", []))
        
        # Get ALL entities in this domain (no filtering)
        available = []
        for state in self.hass.states.async_all():
            if state.entity_id.startswith(f"{domain}."):
                available.append({
                    "entity_id": state.entity_id,
                    "friendly_name": state.attributes.get("friendly_name", state.entity_id),
                    "state": state.state,
                    "domain": domain,
                })
        
        # Get service schema
        action = task.get("action", "turn_on")
        service_name = self._action_to_service(action)
        
        try:
            descriptions = await self.hass.services.async_get_all_descriptions()
            service_schema = descriptions.get(domain, {}).get(service_name, {})
        except Exception as err:
            _LOGGER.warning("Failed to get service schema for %s.%s: %s", domain, service_name, err)
            service_schema = {}
        
        task["available_entities"] = available
        task["service_schema"] = service_schema
        task["domain"] = domain
        task["status"] = "awaiting_selection"
        
        _LOGGER.info(
            "Resolved device_control: %d entities available in domain '%s'",
            len(available),
            domain,
        )
        
        return task
    
    def _guess_domain(self, targets: list[str]) -> str:
        """Guess HA domain from target names."""
        text = " ".join(targets).lower()
        
        if any(word in text for word in ["lampe", "licht", "light"]):
            return "light"
        if any(word in text for word in ["steckdose", "schalter", "switch", "plug"]):
            return "switch"
        if any(word in text for word in ["cover", "blind", "jalousie", "rollo"]):
            return "cover"
        if any(word in text for word in ["fan", "lüfter", "ventilator"]):
            return "fan"
        
        # Default to light
        return "light"
    
    def _action_to_service(self, action: str) -> str:
        """Convert action to service name."""
        if action == "turn_on":
            return "turn_on"
        elif action == "turn_off":
            return "turn_off"
        elif action == "toggle":
            return "toggle"
        elif action == "set":
            return "turn_on"  # 'set' usually means turn_on with parameters
        else:
            return "turn_on"
    
    def _resolve_shopping_add(self, task: dict[str, Any]) -> dict[str, Any]:
        """Split shopping items deterministically - ALWAYS separate items."""
        raw_items = task.get("raw_items", "")
        
        # Split on: commas, "und", "and", "&"
        items = re.split(r',|\s+(?:und|and)\s+|\s+&\s+', raw_items, flags=re.IGNORECASE)
        
        # Trim, capitalize first letter, remove empty
        items = [item.strip().capitalize() for item in items if item.strip()]
        
        task["items"] = items
        task["status"] = "ready_for_execution"
        
        _LOGGER.info(
            "Resolved shopping_add: '%s' → %d item(s): %s",
            raw_items,
            len(items),
            items,
        )
        
        return task
    
    def _resolve_calendar_query(self, task: dict[str, Any]) -> dict[str, Any]:
        """Parse dates for calendar query."""
        start = task.get("start")
        end = task.get("end")
        
        start_dt = self._parse_date(start) if start else datetime.now()
        end_dt = self._parse_date(end) if end else start_dt + timedelta(days=7)
        
        # Handle same start and end (e.g., "tomorrow" to "tomorrow" means that day)
        if start and end and start == end:
            end_dt = start_dt + timedelta(days=1)
        
        task["start_iso"] = start_dt.isoformat()
        task["end_iso"] = end_dt.isoformat()
        task["status"] = "ready_for_execution"
        
        _LOGGER.info(
            "Resolved calendar_query: %s to %s → %s to %s",
            start,
            end,
            start_dt.date(),
            end_dt.date(),
        )
        
        return task
    
    async def _resolve_calendar_create(self, task: dict[str, Any]) -> dict[str, Any]:
        """Parse dates and provide available calendars for event creation."""
        # Parse dates
        start = task.get("start", "")
        end = task.get("end", "")
        
        start_dt = self._parse_date(start) if start else datetime.now()
        end_dt = self._parse_date(end) if end else start_dt + timedelta(hours=1)
        
        task["start_iso"] = start_dt.isoformat()
        task["end_iso"] = end_dt.isoformat()
        
        # Get available calendars
        available_calendars = []
        for state in self.hass.states.async_all():
            if state.entity_id.startswith("calendar."):
                available_calendars.append({
                    "entity_id": state.entity_id,
                    "friendly_name": state.attributes.get("friendly_name", state.entity_id),
                })
        
        if available_calendars:
            task["available_calendars"] = available_calendars
            task["status"] = "awaiting_selection"
            _LOGGER.info(
                "Resolved calendar_create: %d calendar(s) available",
                len(available_calendars),
            )
        else:
            # No calendars available, mark as ready but will fail in execution
            task["status"] = "ready_for_execution"
            _LOGGER.warning("No calendars available for event creation")
        
        return task
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse a date string to datetime."""
        if not date_str:
            return datetime.now()
        
        date_lower = date_str.lower().strip()
        now = datetime.now()
        
        # Handle relative dates
        if date_lower in ("today", "heute"):
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_lower in ("tomorrow", "morgen"):
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_lower in ("yesterday", "gestern"):
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Try to parse ISO format
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass
        
        # TODO: Handle more complex dates like "next Friday"
        # For now, default to now
        _LOGGER.warning("Could not parse date '%s', using current time", date_str)
        return now
