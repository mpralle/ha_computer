"""Shopping list API interface for Llama.cpp Assist integration."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components import shopping_list

from .tools import Tool

_LOGGER = logging.getLogger(__name__)


class ShoppingAddItemTool(Tool):
    """Tool to add an item to the shopping list."""

    @property
    def name(self) -> str:
        return "shopping_add_item"

    @property
    def description(self) -> str:
        return "Add an item to the shopping list"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "The item to add to the shopping list",
                }
            },
            "required": ["item"],
        }

    async def async_call(self, item: str, **kwargs) -> dict[str, Any]:
        """Add item to shopping list."""
        try:
            # Be forgiving: split on common separators like commas, "and", "und"
            # Examples:
            #   "käse und wein" -> ["käse", "wein"]
            #   "milk, eggs, bread" -> ["milk", "eggs", "bread"]
            #   "milk and eggs" -> ["milk", "eggs"]
            items = re.split(r',|\s+(?:and|und)\s+', item)
            items = [i.strip() for i in items if i.strip()]
            
            if not items:
                return {
                    "success": False,
                    "error": "No valid items to add",
                }
            
            # Add each item separately
            added_items = []
            for single_item in items:
                await self.hass.services.async_call(
                    "shopping_list",
                    "add_item",
                    {"name": single_item},
                    blocking=True,
                )
                added_items.append(single_item)
            
            if len(added_items) == 1:
                message = f"Added '{added_items[0]}' to shopping list"
            else:
                message = f"Added {len(added_items)} items to shopping list: {', '.join(added_items)}"
            
            return {
                "success": True,
                "message": message,
            }
            
        except Exception as err:
            _LOGGER.error("Failed to add item to shopping list: %s", err)
            return {
                "success": False,
                "error": str(err),
            }


class ShoppingRemoveItemTool(Tool):
    """Tool to remove an item from the shopping list."""

    @property
    def name(self) -> str:
        return "shopping_remove_item"

    @property
    def description(self) -> str:
        return "Remove an item from the shopping list (uses fuzzy matching)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "item": {
                    "type": "string",
                    "description": "The item to remove from the shopping list",
                }
            },
            "required": ["item"],
        }

    async def async_call(self, item: str, **kwargs) -> dict[str, Any]:
        """Remove item from shopping list."""
        try:
            # Get current shopping list items
            items = await self._get_shopping_list_items()
            
            # Find matching item (case-insensitive)
            item_lower = item.lower()
            matching_item = None
            
            for list_item in items:
                if item_lower in list_item["name"].lower():
                    matching_item = list_item
                    break
            
            if not matching_item:
                return {
                    "success": False,
                    "error": f"Item '{item}' not found in shopping list",
                }
            
            # Remove the item
            await self.hass.services.async_call(
                "shopping_list",
                "complete_item",
                {"item": matching_item["name"]},
                blocking=True,
            )
            
            return {
                "success": True,
                "message": f"Removed '{matching_item['name']}' from shopping list",
            }
            
        except Exception as err:
            _LOGGER.error("Failed to remove item from shopping list: %s", err)
            return {
                "success": False,
                "error": str(err),
            }

    async def _get_shopping_list_items(self) -> list[dict[str, Any]]:
        """Get all shopping list items."""
        # Try to get shopping list data
        if "shopping_list" in self.hass.data:
            data = self.hass.data["shopping_list"]
            if hasattr(data, "items"):
                return [{"name": item["name"], "id": item.get("id")} for item in data.items]
        
        return []


class ShoppingListAllTool(Tool):
    """Tool to list all shopping list items."""

    @property
    def name(self) -> str:
        return "shopping_list_all"

    @property
    def description(self) -> str:
        return "Get all items on the shopping list"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def async_call(self, **kwargs) -> dict[str, Any]:
        """Get all shopping list items."""
        try:
            items = await self._get_shopping_list_items()
            
            return {
                "success": True,
                "items": [item["name"] for item in items],
                "count": len(items),
            }
            
        except Exception as err:
            _LOGGER.error("Failed to get shopping list: %s", err)
            return {
                "success": False,
                "error": str(err),
            }

    async def _get_shopping_list_items(self) -> list[dict[str, Any]]:
        """Get all shopping list items."""
        if "shopping_list" in self.hass.data:
            data = self.hass.data["shopping_list"]
            if hasattr(data, "items"):
                return [
                    {"name": item["name"], "id": item.get("id"), "complete": item.get("complete", False)}
                    for item in data.items
                    if not item.get("complete", False)
                ]
        
        return []
