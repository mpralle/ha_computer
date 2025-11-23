"""Memory storage for Llama.cpp Assist integration."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class MemoryStorage:
    """Manage persistent memory storage for the assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize memory storage."""
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {
            "preferences": {},
            "facts": {},
            "history_summaries": [],
            "custom": {},
        }

    async def async_load(self) -> None:
        """Load memory from storage."""
        try:
            stored_data = await self._store.async_load()
            if stored_data:
                self._data = stored_data
                _LOGGER.debug("Loaded memory from storage: %s keys", len(self._data))
            else:
                _LOGGER.debug("No existing memory found, using defaults")
        except Exception as err:
            _LOGGER.error("Failed to load memory: %s", err)

    async def async_save(self) -> None:
        """Save memory to storage."""
        try:
            await self._store.async_save(self._data)
            _LOGGER.debug("Saved memory to storage")
        except Exception as err:
            _LOGGER.error("Failed to save memory: %s", err)

    def read(self, key: str) -> Any:
        """Read a value from memory using dot notation (e.g., 'preferences.light_color')."""
        try:
            keys = key.split(".")
            value = self._data
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return None
            return value
        except Exception as err:
            _LOGGER.error("Failed to read memory key '%s': %s", key, err)
            return None

    async def write(self, key: str, value: Any) -> bool:
        """Write a value to memory using dot notation."""
        try:
            keys = key.split(".")
            data = self._data
            
            # Navigate to the parent dict
            for k in keys[:-1]:
                if k not in data:
                    data[k] = {}
                data = data[k]
            
            # Set the value
            data[keys[-1]] = value
            
            # Save to disk
            await self.async_save()
            _LOGGER.debug("Wrote memory key '%s' = %s", key, value)
            return True
        except Exception as err:
            _LOGGER.error("Failed to write memory key '%s': %s", key, err)
            return False

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all available keys, optionally filtered by prefix."""
        keys = []
        
        def recurse(data: dict, path: str = ""):
            for key, value in data.items():
                full_key = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    recurse(value, full_key)
                else:
                    keys.append(full_key)
        
        recurse(self._data)
        
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        
        return keys

    def get_context_summary(self, max_items: int = 10) -> str:
        """Get a formatted summary of memory for system prompt injection."""
        lines = []
        
        # Add preferences
        if self._data.get("preferences"):
            lines.append("User preferences:")
            for key, value in list(self._data["preferences"].items())[:max_items]:
                lines.append(f"  - {key}: {value}")
        
        # Add facts
        if self._data.get("facts"):
            lines.append("Known facts:")
            for key, value in list(self._data["facts"].items())[:max_items]:
                lines.append(f"  - {key}: {value}")
        
        # Add recent history summaries
        if self._data.get("history_summaries"):
            lines.append("Recent interactions:")
            for summary in self._data["history_summaries"][-3:]:
                lines.append(f"  - {summary}")
        
        return "\n".join(lines) if lines else "No memory stored yet."

    def get_all_data(self) -> dict[str, Any]:
        """Get all memory data (for debugging/export)."""
        return self._data.copy()

    async def clear_all(self) -> None:
        """Clear all memory (use with caution)."""
        self._data = {
            "preferences": {},
            "facts": {},
            "history_summaries": [],
            "custom": {},
        }
        await self.async_save()
        _LOGGER.warning("Cleared all memory")
