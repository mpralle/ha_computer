"""Calendar API interface for Llama.cpp Assist integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .tools import Tool

_LOGGER = logging.getLogger(__name__)


class CalendarListEventsTool(Tool):
    """Tool to list calendar events."""

    @property
    def name(self) -> str:
        return "calendar_list_events"

    @property
    def description(self) -> str:
        return "List upcoming calendar events within a date range"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "description": "Start date/time (ISO format or relative like 'today', 'tomorrow')",
                },
                "end": {
                    "type": "string",
                    "description": "End date/time (ISO format or relative like 'today', 'tomorrow')",
                },
                "calendar_entity": {
                    "type": "string",
                    "description": "Specific calendar entity ID to query (optional, queries all if not specified)",
                },
            },
            "required": [],
        }

    async def async_call(
        self,
        start: str | None = None,
        end: str | None = None,
        calendar_entity: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """List calendar events."""
        try:
            # Parse dates
            start_dt = self._parse_date(start) if start else datetime.now()
            end_dt = self._parse_date(end) if end else start_dt + timedelta(days=7)
            
            # Get calendar entities
            calendar_entities = []
            if calendar_entity:
                calendar_entities = [calendar_entity]
            else:
                # Find all calendar entities
                for state in self.hass.states.async_all():
                    if state.entity_id.startswith("calendar."):
                        calendar_entities.append(state.entity_id)
            
            if not calendar_entities:
                return {
                    "success": False,
                    "error": "No calendar entities found",
                }
            
            # Get events from each calendar
            all_events = []
            for entity_id in calendar_entities:
                state = self.hass.states.get(entity_id)
                if state:
                    # Try to get events using the calendar component
                    events = await self._get_calendar_events(entity_id, start_dt, end_dt)
                    all_events.extend(events)
            
            # Sort by start time
            all_events.sort(key=lambda x: x.get("start", ""))
            
            return {
                "success": True,
                "events": all_events,
                "count": len(all_events),
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
            }
            
        except Exception as err:
            _LOGGER.error("Failed to list calendar events: %s", err)
            return {
                "success": False,
                "error": str(err),
            }

    async def _get_calendar_events(
        self, entity_id: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        """Get events from a calendar entity.

        Tries the calendar helper API first (preferred),
        then falls back to the calendar.get_events service.
        Returns a list of plain dicts for the LLM.
        """
        events: list[Any] = []

        # --- 1) Preferred: use the calendar helper API ---
        try:
            # async_get_events is the canonical API used by calendar platforms
            events = await calendar_component.async_get_events(
                self.hass,
                entity_id,
                start,
                end,
            )
            _LOGGER.debug(
                "Got %d events from calendar helper for %s", len(events), entity_id
            )
        except Exception as err:  # noqa: BLE001 - we want a broad fallback
            _LOGGER.debug(
                "Calendar helper async_get_events failed for %s: %s – falling back to service",
                entity_id,
                err,
            )

        # --- 2) Fallback: use the calendar.get_events service ---
        if not events:
            try:
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": entity_id,
                        "start_date_time": start.isoformat(),
                        "end_date_time": end.isoformat(),
                    },
                    blocking=True,
                    return_response=True,
                )

                if response and entity_id in response:
                    events = response[entity_id].get("events", []) or []
                    _LOGGER.debug(
                        "Got %d events from calendar.get_events service for %s",
                        len(events),
                        entity_id,
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "Could not get events from %s via service: %s", entity_id, err
                )
                return []

        # --- 3) Normalise events to plain dicts ---
        normalised: list[dict[str, Any]] = []

        for ev in events:
            # If the calendar platform already returned dicts, keep them
            if isinstance(ev, dict):
                normalised.append(ev)
                continue

            # Otherwise, try to map a CalendarEvent-like object to a dict
            start_val = getattr(ev, "start", None)
            end_val = getattr(ev, "end", None)

            if isinstance(start_val, datetime):
                start_str = start_val.isoformat()
            else:
                start_str = str(start_val) if start_val is not None else None

            if isinstance(end_val, datetime):
                end_str = end_val.isoformat()
            else:
                end_str = str(end_val) if end_val is not None else None

            normalised.append(
                {
                    "summary": getattr(ev, "summary", "") or "",
                    "description": getattr(ev, "description", "") or "",
                    "location": getattr(ev, "location", "") or "",
                    "start": start_str,
                    "end": end_str,
                    # If your platform exposes more fields (e.g. uid, all_day, etc.),
                    # you can add them here.
                }
            )

        return normalised

    def _parse_date(self, date_str: str) -> datetime:
        """Parse a date string to datetime."""
        # Handle relative dates
        now = datetime.now()
        
        if date_str.lower() == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_str.lower() == "tomorrow":
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_str.lower() == "yesterday":
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Try to parse ISO format
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass
        
        # Default to now
        return now


class CalendarCreateEventTool(Tool):
    """Tool to create a calendar event."""

    @property
    def name(self) -> str:
        return "calendar_create_event"

    @property
    def description(self) -> str:
        return "Create a new calendar event"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "calendar_entity": {
                    "type": "string",
                    "description": "Calendar entity ID to add the event to",
                },
                "title": {
                    "type": "string",
                    "description": "Event title/summary",
                },
                "start": {
                    "type": "string",
                    "description": "Start date/time (ISO format)",
                },
                "end": {
                    "type": "string",
                    "description": "End date/time (ISO format)",
                },
                "description": {
                    "type": "string",
                    "description": "Event description (optional)",
                },
            },
            "required": ["calendar_entity", "title", "start", "end"],
        }

    async def async_call(
        self,
        calendar_entity: str,
        title: str,
        start: str,
        end: str,
        description: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Create a calendar event."""
        try:
            service_data = {
                "entity_id": calendar_entity,
                "summary": title,
                "start_date_time": start,
                "end_date_time": end,
            }
            
            if description:
                service_data["description"] = description
            
            await self.hass.services.async_call(
                "calendar",
                "create_event",
                service_data,
                blocking=True,
            )
            
            return {
                "success": True,
                "message": f"Created event '{title}' on {calendar_entity}",
            }
            
        except Exception as err:
            _LOGGER.error("Failed to create calendar event: %s", err)
            return {
                "success": False,
                "error": str(err),
            }
