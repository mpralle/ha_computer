"""Executor Agent: Executes concrete tasks against Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class TaskExecutor:
    """
    Agent that executes concrete tasks with selected entities.
    
    This agent only executes - no reasoning or decision making.
    """
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Task Executor."""
        self.hass = hass
    
    async def execute_tasks(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Execute tasks and return execution report.
        
        Args:
            tasks: List of concrete tasks with selected entities
        
        Returns:
            Execution report with results for each operation
        """
        results = []
        executed_signatures = set()
        
        for task in tasks:
            if task.get("status") != "ready_for_execution":
                # Skip tasks that aren't ready
                _LOGGER.warning(
                    "Skipping task %s with status %s",
                    task.get("id"),
                    task.get("status"),
                )
                continue
            
            task_results = await self._execute_task(task, executed_signatures)
            results.extend(task_results)
        
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        report = {
            "total_tasks": len(tasks),
            "successful_operations": successful,
            "failed_operations": failed,
            "results": results,
        }
        
        _LOGGER.info(
            "Execution complete: %d successful, %d failed",
            successful,
            failed,
        )
        
        return report
    
    async def _execute_task(
        self,
        task: dict[str, Any],
        executed_signatures: set[str],
    ) -> list[dict[str, Any]]:
        """Execute a single task and return results."""
        task_type = task.get("type")
        task_id = task.get("id", "unknown")
        
        if task_type == "device_control":
            return await self._execute_device_control(task, executed_signatures)
        elif task_type == "shopping_add":
            return await self._execute_shopping_add(task)
        elif task_type == "shopping_query":
            return await self._execute_shopping_query(task)
        elif task_type == "shopping_remove":
            return await self._execute_shopping_remove(task)
        elif task_type == "calendar_query":
            return await self._execute_calendar_query(task)
        elif task_type == "calendar_create":
            return await self._execute_calendar_create(task)
        elif task_type == "memory_read":
            return await self._execute_memory_read(task)
        elif task_type == "memory_write":
            return await self._execute_memory_write(task)
        else:
            _LOGGER.error("Unknown task type: %s", task_type)
            return [{
                "task_id": task_id,
                "task_type": task_type,
                "success": False,
                "error": f"Unknown task type: {task_type}",
            }]
    
    async def _execute_device_control(
        self,
        task: dict[str, Any],
        executed_signatures: set[str],
    ) -> list[dict[str, Any]]:
        """Execute device control task."""
        results = []
        task_id = task.get("id", "unknown")
        selected_entities = task.get("selected_entities", [])
        service_data_template = task.get("service_data", {})
        
        if not selected_entities:
            return [{
                "task_id": task_id,
                "task_type": "device_control",
                "success": False,
                "error": "No entities selected",
            }]
        
        domain = service_data_template.get("domain", "light")
        service = service_data_template.get("service", "turn_on")
        extra_data = service_data_template.get("data", {})
        
        for entity_id in selected_entities:
            # Deduplication check
            sig = f"{domain}.{service}:{entity_id}"
            
            if sig in executed_signatures:
                results.append({
                    "task_id": task_id,
                    "task_type": "device_control",
                    "operation": f"{domain}.{service}",
                    "entity": entity_id,
                    "success": True,
                    "skipped": "duplicate",
                })
                continue
            
            try:
                await self.hass.services.async_call(
                    domain,
                    service,
                    {"entity_id": entity_id, **extra_data},
                    blocking=True,
                )
                results.append({
                    "task_id": task_id,
                    "task_type": "device_control",
                    "operation": f"{domain}.{service}",
                    "entity": entity_id,
                    "success": True,
                })
                executed_signatures.add(sig)
                _LOGGER.debug("Executed: %s on %s", service, entity_id)
                
            except Exception as err:
                _LOGGER.error("Failed to execute %s on %s: %s", service, entity_id, err)
                results.append({
                    "task_id": task_id,
                    "task_type": "device_control",
                    "operation": f"{domain}.{service}",
                    "entity": entity_id,
                    "success": False,
                    "error": str(err),
                })
        
        return results
    
    async def _execute_shopping_add(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute shopping add task."""
        results = []
        task_id = task.get("id", "unknown")
        items = task.get("items", [])
        
        for item in items:
            try:
                await self.hass.services.async_call(
                    "shopping_list",
                    "add_item",
                    {"name": item},
                    blocking=True,
                )
                results.append({
                    "task_id": task_id,
                    "task_type": "shopping_add",
                    "operation": "shopping_add",
                    "item": item,
                    "success": True,
                })
                _LOGGER.debug("Added to shopping list: %s", item)
                
            except Exception as err:
                _LOGGER.error("Failed to add shopping item %s: %s", item, err)
                results.append({
                    "task_id": task_id,
                    "task_type": "shopping_add",
                    "operation": "shopping_add",
                    "item": item,
                    "success": False,
                    "error": str(err),
                })
        
        return results
    
    async def _execute_shopping_query(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute shopping query task."""
        task_id = task.get("id", "unknown")
        
        try:
            # Get shopping list data
            if "shopping_list" in self.hass.data:
                data = self.hass.data["shopping_list"]
                if hasattr(data, "items"):
                    items = [
                        item["name"]
                        for item in data.items
                        if not item.get("complete", False)
                    ]
                    return [{
                        "task_id": task_id,
                        "task_type": "shopping_query",
                        "operation": "shopping_query",
                        "items": items,
                        "success": True,
                    }]
            
            return [{
                "task_id": task_id,
                "task_type": "shopping_query",
                "operation": "shopping_query",
                "items": [],
                "success": True,
            }]
            
        except Exception as err:
            _LOGGER.error("Failed to query shopping list: %s", err)
            return [{
                "task_id": task_id,
                "task_type": "shopping_query",
                "operation": "shopping_query",
                "success": False,
                "error": str(err),
            }]
    
    async def _execute_shopping_remove(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute shopping remove task."""
        task_id = task.get("id", "unknown")
        item_to_remove = task.get("item", "")
        
        # This would need access to shopping list - simplified for now
        return [{
            "task_id": task_id,
            "task_type": "shopping_remove",
            "operation": "shopping_remove",
            "item": item_to_remove,
            "success": False,
            "error": "Shopping remove not yet fully implemented",
        }]
    
    async def _execute_calendar_query(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute calendar query task."""
        task_id = task.get("id", "unknown")
        start_iso = task.get("start_iso")
        end_iso = task.get("end_iso")
        
        if not start_iso or not end_iso:
            return [{
                "task_id": task_id,
                "task_type": "calendar_query",
                "operation": "calendar_query",
                "success": False,
                "error": "Missing start or end date",
            }]
        
        # Get all calendar entities
        calendar_entities = [
            state.entity_id
            for state in self.hass.states.async_all()
            if state.entity_id.startswith("calendar.")
        ]
        
        if not calendar_entities:
            return [{
                "task_id": task_id,
                "task_type": "calendar_query",
                "operation": "calendar_query",
                "events": [],
                "success": True,
                "message": "No calendars found",
            }]
        
        # Query events from all calendars
        all_events = []
        
        for calendar_entity in calendar_entities:
            try:
                # Use calendar.get_events service to fetch events
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": calendar_entity,
                        "start_date_time": start_iso,
                        "end_date_time": end_iso,
                    },
                    blocking=True,
                    return_response=True,
                )
                
                # Extract events from response
                if response and calendar_entity in response:
                    events = response[calendar_entity].get("events", [])
                    for event in events:
                        all_events.append({
                            "calendar": calendar_entity,
                            "summary": event.get("summary", ""),
                            "start": event.get("start", ""),
                            "end": event.get("end", ""),
                            "description": event.get("description", ""),
                            "location": event.get("location", ""),
                        })
                
            except Exception as err:
                _LOGGER.warning(
                    "Failed to query calendar %s: %s",
                    calendar_entity,
                    err
                )
                continue
        
        _LOGGER.info(
            "Found %d calendar events between %s and %s",
            len(all_events),
            start_iso[:10],
            end_iso[:10]
        )
        
        return [{
            "task_id": task_id,
            "task_type": "calendar_query",
            "operation": "calendar_query",
            "events": all_events,
            "event_count": len(all_events),
            "success": True,
        }]
    
    async def _execute_calendar_create(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute calendar create task."""
        task_id = task.get("id", "unknown")
        selected_calendar = task.get("selected_calendar")
        
        if not selected_calendar:
            return [{
                "task_id": task_id,
                "task_type": "calendar_create",
                "success": False,
                "error": "No calendar selected",
            }]
        
        try:
            service_data = {
                "entity_id": selected_calendar,
                "summary": task.get("summary", ""),
                "start_date_time": task.get("start_iso", ""),
                "end_date_time": task.get("end_iso", ""),
            }
            
            if task.get("description"):
                service_data["description"] = task["description"]
            if task.get("location"):
                service_data["location"] = task["location"]
            
            await self.hass.services.async_call(
                "calendar",
                "create_event",
                service_data,
                blocking=True,
            )
            
            return [{
                "task_id": task_id,
                "task_type": "calendar_create",
                "operation": "calendar_create",
                "calendar": selected_calendar,
                "summary": task.get("summary"),
                "success": True,
            }]
            
        except Exception as err:
            _LOGGER.error("Failed to create calendar event: %s", err)
            return [{
                "task_id": task_id,
                "task_type": "calendar_create",
                "operation": "calendar_create",
                "success": False,
                "error": str(err),
            }]
    
    async def _execute_memory_read(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute memory read task."""
        task_id = task.get("id", "unknown")
        
        # Memory operations would need memory storage reference
        return [{
            "task_id": task_id,
            "task_type": "memory_read",
            "operation": "memory_read",
            "success": False,
            "error": "Memory operations not yet integrated",
        }]
    
    async def _execute_memory_write(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute memory write task."""
        task_id = task.get("id", "unknown")
        
        # Memory operations would need memory storage reference
        return [{
            "task_id": task_id,
            "task_type": "memory_write",
            "operation": "memory_write",
            "success": False,
            "error": "Memory operations not yet integrated",
        }]
