"""Tool/function calling framework for Llama.cpp Assist integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import logging
from typing import Any, TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import re

if TYPE_CHECKING:
    from .memory import MemoryStorage

_LOGGER = logging.getLogger(__name__)


class Tool(ABC):
    """Base class for tools that can be called by the LLM."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the tool."""
        self.hass = hass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the tool description."""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Return the OpenAI function schema for parameters."""

    @abstractmethod
    async def async_call(self, **kwargs) -> dict[str, Any]:
        """Execute the tool and return results."""

    def get_schema(self) -> dict[str, Any]:
        """Get the complete OpenAI function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a new tool."""
        self._tools[tool.name] = tool
        _LOGGER.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI function schemas for all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    def get_all_tools(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())


# === Home Assistant Core Tools ===


class GetStateTool(Tool):
    """Tool to get the state of an entity."""

    @property
    def name(self) -> str:
        return "get_state"

    @property
    def description(self) -> str:
        return "Get the current state and attributes of a Home Assistant entity"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The entity ID (e.g., 'light.living_room')",
                }
            },
            "required": ["entity_id"],
        }

    async def async_call(self, entity_id: str, **kwargs) -> dict[str, Any]:
        """Get entity state."""
        state = self.hass.states.get(entity_id)
        
        if state is None:
            return {
                "success": False,
                "error": f"Entity {entity_id} not found",
            }
        
        return {
            "success": True,
            "entity_id": entity_id,
            "state": state.state,
            "attributes": dict(state.attributes),
        }


class ListEntitiesTool(Tool):
    """Tool to list available entities."""

    @property
    def name(self) -> str:
        return "list_entities"

    @property
    def description(self) -> str:
        return (
            "List Home Assistant entities, optionally filtered by domain, area, "
            "or a substring of the friendly name. "
            "For device control, you should normally filter by domain "
            "(e.g. 'light', 'switch')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": (
                        "Optional: Filter by domain (e.g., 'light', 'switch', 'sensor'). "
                        "For turning things on/off, this should typically be 'light' or 'switch'."
                    ),
                },
                "area": {
                    "type": "string",
                    "description": (
                        "Optional: Filter by area name (e.g., 'living room', 'bedroom')."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Optional: Case-insensitive substring match against the entity "
                        "friendly_name. For example, 'Schrank' matches 'Schranklampe'."
                    ),
                },
            },
            "required": [],
        }

    async def async_call(
        self,
        domain: str | None = None,
        area: str | None = None,
        name: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """List entities."""
        from homeassistant.helpers import area_registry, entity_registry

        ent_reg = entity_registry.async_get(self.hass)
        area_reg = area_registry.async_get(self.hass)

        # If the model doesn't specify a domain, restrict to common controllable domains
        # so it doesn't get flooded with sensors/weather/system entities.
        allowed_default_domains = {
            "light",
            "switch",
            "cover",
            "fan",
            "media_player",
            "climate",
        }

        entities: list[dict[str, Any]] = []

        name_filter = name.lower() if name else None

        for state in self.hass.states.async_all():
            entity_id = state.entity_id
            entity_domain = entity_id.split(".")[0]

            # Domain filtering
            if domain:
                if entity_domain != domain:
                    continue
            else:
                # No explicit domain: if no area is specified, restrict to controllable domains
                if not area and entity_domain not in allowed_default_domains:
                    continue

            # Area filtering
            if area:
                entity_entry = ent_reg.async_get(entity_id)
                if entity_entry and entity_entry.area_id:
                    area_entry = area_reg.async_get_area(entity_entry.area_id)
                    if not area_entry or area_entry.name.lower() != area.lower():
                        continue
                else:
                    # If we require an area but can't resolve one, skip this entity
                    continue

            friendly_name = state.attributes.get("friendly_name", entity_id)

            # Name / friendly_name filtering
            if name_filter and name_filter not in friendly_name.lower():
                continue

            entities.append(
                {
                    "entity_id": entity_id,
                    "state": state.state,
                    "friendly_name": friendly_name,
                    "domain": entity_domain,
                }
            )

            if len(entities) >= 50:
                break

        return {
            "success": True,
            "count": len(entities),
            "entities": entities,
        }



class CallServiceTool(Tool):
    """Tool to call Home Assistant services."""

    @property
    def name(self) -> str:
        return "call_service"

    @property
    def description(self) -> str:
        return "Call a Home Assistant service to control devices (e.g., turn on lights, set temperature)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": (
                        "Service domain (e.g., 'light', 'switch', 'climate'). "
                        "Use the SAME domain as in the target entity_id (e.g. 'light' for light.xxx)."
                    ),
                },
                "service": {
                    "type": "string",
                    "description": (
                        "Service name (e.g., 'turn_on', 'turn_off', 'set_temperature'). "
                        "If you are unsure about the fields for a service, FIRST call 'describe_service'."
                    ),
                },
                "entity_id": {
                    "type": "string",
                    "description": (
                        "Target entity ID. "
                        "You SHOULD pass a single entity_id. "
                        "If you accidentally pass multiple IDs separated by commas or whitespace, "
                        "the tool will split them into a list."
                    ),
                },
                "data": {
                    "type": "object",
                    "description": "Additional service data (e.g., brightness, temperature)",
                },
            },
            "required": ["domain", "service"],
        }

    async def async_call(
        self,
        domain: str,
        service: str,
        entity_id: str | None = None,
        data: dict[str, Any] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """Call a service."""
        try:
            service_data: dict[str, Any] = data or {}

            if entity_id:
                # Be forgiving: support comma/whitespace separated lists of entity_ids
                # Examples:
                #   "light.a,light.b"
                #   "light.a, light.b"
                #   "light.a light.b"
                parts = [p.strip() for p in re.split(r"[,\s]+", entity_id) if p.strip()]

                if len(parts) == 1:
                    service_data["entity_id"] = parts[0]
                elif len(parts) > 1:
                    service_data["entity_id"] = parts

            await self.hass.services.async_call(
                domain,
                service,
                service_data,
                blocking=True,
            )

            return {
                "success": True,
                "message": f"Called {domain}.{service}",
            }

        except Exception as err:
            _LOGGER.error("Service call failed: %s", err)
            return {
                "success": False,
                "error": str(err),
            }



# === Utility Tools ===


class GetTimeTool(Tool):
    """Tool to get current time."""

    @property
    def name(self) -> str:
        return "get_time"

    @property
    def description(self) -> str:
        return "Get the current time"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def async_call(self, **kwargs) -> dict[str, Any]:
        """Get current time."""
        now = datetime.now()
        return {
            "success": True,
            "time": now.strftime("%H:%M:%S"),
            "timestamp": now.isoformat(),
        }


class GetDateTool(Tool):
    """Tool to get current date."""

    @property
    def name(self) -> str:
        return "get_date"

    @property
    def description(self) -> str:
        return "Get the current date"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def async_call(self, **kwargs) -> dict[str, Any]:
        """Get current date."""
        now = datetime.now()
        return {
            "success": True,
            "date": now.strftime("%Y-%m-%d"),
            "day_of_week": now.strftime("%A"),
            "timestamp": now.isoformat(),
        }


class GetDateTimeTool(Tool):
    """Tool to get current date and time."""

    @property
    def name(self) -> str:
        return "get_datetime"

    @property
    def description(self) -> str:
        return "Get the current date and time"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def async_call(self, **kwargs) -> dict[str, Any]:
        """Get current datetime."""
        now = datetime.now()
        return {
            "success": True,
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "timestamp": now.isoformat(),
        }


# === Memory Tools ===


class MemoryReadTool(Tool):
    """Tool to read from memory."""

    def __init__(self, hass: HomeAssistant, memory: MemoryStorage) -> None:
        """Initialize with memory storage."""
        super().__init__(hass)
        self.memory = memory

    @property
    def name(self) -> str:
        return "memory_read"

    @property
    def description(self) -> str:
        return "Read a value from persistent memory storage"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Memory key to read (supports dot notation like 'preferences.light_color')",
                }
            },
            "required": ["key"],
        }

    async def async_call(self, key: str, **kwargs) -> dict[str, Any]:
        """Read from memory."""
        value = self.memory.read(key)
        
        if value is None:
            return {
                "success": False,
                "error": f"No value found for key '{key}'",
            }
        
        return {
            "success": True,
            "key": key,
            "value": value,
        }


class MemoryWriteTool(Tool):
    """Tool to write to memory."""

    def __init__(self, hass: HomeAssistant, memory: MemoryStorage) -> None:
        """Initialize with memory storage."""
        super().__init__(hass)
        self.memory = memory

    @property
    def name(self) -> str:
        return "memory_write"

    @property
    def description(self) -> str:
        return "Write a value to persistent memory storage"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Memory key to write (supports dot notation like 'preferences.light_color')",
                },
                "value": {
                    "type": "string",
                    "description": "Value to store",
                },
            },
            "required": ["key", "value"],
        }

    async def async_call(self, key: str, value: str, **kwargs) -> dict[str, Any]:
        """Write to memory."""
        success = await self.memory.write(key, value)
        
        if not success:
            return {
                "success": False,
                "error": "Failed to write to memory",
            }
        
        return {
            "success": True,
            "message": f"Stored '{key}' = '{value}'",
        }


class MemoryListKeysTool(Tool):
    """Tool to list memory keys."""

    def __init__(self, hass: HomeAssistant, memory: MemoryStorage) -> None:
        """Initialize with memory storage."""
        super().__init__(hass)
        self.memory = memory

    @property
    def name(self) -> str:
        return "memory_list_keys"

    @property
    def description(self) -> str:
        return "List all available memory keys"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def async_call(self, **kwargs) -> dict[str, Any]:
        """List memory keys."""
        keys = self.memory.list_keys()
        
        return {
            "success": True,
            "keys": keys,
            "count": len(keys),
        }
    
class DescribeServiceTool(Tool):
    """Tool to inspect Home Assistant service schema and fields."""

    @property
    def name(self) -> str:
        return "describe_service"

    @property
    def description(self) -> str:
        return (
            "Get information about a Home Assistant service: its description, "
            "required/optional fields, and example data. Use this if you are "
            "unsure how to call a specific service."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Service domain (e.g., 'light', 'switch', 'climate')",
                },
                "service": {
                    "type": "string",
                    "description": "Service name (e.g., 'turn_on', 'turn_off', 'set_temperature')",
                },
            },
            "required": ["domain", "service"],
        }

    async def async_call(
        self,
        domain: str,
        service: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return description for a given service."""
        try:
            # async_get_all_descriptions returns a nested dict: {domain: {service: {...}}}
            descriptions = await self.hass.services.async_get_all_descriptions()
            domain_info = descriptions.get(domain, {})
            service_info = domain_info.get(service)

            if not service_info:
                return {
                    "success": False,
                    "error": f"Service {domain}.{service} not found",
                }

            return {
                "success": True,
                "domain": domain,
                "service": service,
                "description": service_info,
            }

        except Exception as err:
            _LOGGER.error("describe_service failed: %s", err)
            return {
                "success": False,
                "error": str(err),
            }



def create_tool_registry(hass: HomeAssistant, memory: MemoryStorage) -> ToolRegistry:
    """Create and populate the tool registry."""
    registry = ToolRegistry()
    
    # Home Assistant core tools
    registry.register(GetStateTool(hass))
    registry.register(ListEntitiesTool(hass))
    registry.register(CallServiceTool(hass))
    registry.register(DescribeServiceTool(hass))
    
    # Utility tools
    registry.register(GetTimeTool(hass))
    registry.register(GetDateTool(hass))
    registry.register(GetDateTimeTool(hass))
    
    # Memory tools
    registry.register(MemoryReadTool(hass, memory))
    registry.register(MemoryWriteTool(hass, memory))
    registry.register(MemoryListKeysTool(hass, memory))
    
    return registry
