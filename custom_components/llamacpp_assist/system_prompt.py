"""System prompt generation for Llama.cpp Assist integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, entity_registry

if TYPE_CHECKING:
    from .memory import MemoryStorage

_LOGGER = logging.getLogger(__name__)


def generate_hermes_system_prompt(
    hass: HomeAssistant,
    memory: MemoryStorage,
    custom_prefix: str | None,
    max_entities: int,
    tool_schemas: list[dict],
) -> str:
    """Generate system prompt in Hermes-style format with tool definitions."""
    import json

    lines: list[str] = []

    # Custom prefix if provided
    if custom_prefix:
        lines.append(custom_prefix)
        lines.append("")

    # --- Role description ---
    lines.append("You are a helpful home assistant butler. Control devices, manage shopping lists, and handle calendar events using the provided tools.")
    lines.append("")

    # --- Current time and date ---
    now = datetime.now()
    lines.append(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Day of week: {now.strftime('%A')}")
    lines.append("")

    # --- Tool schemas ---
    lines.append("Available tools:")
    lines.append("<tools>")
    for schema in tool_schemas:
        if "function" in schema:
            lines.append(json.dumps(schema["function"]))
    lines.append("</tools>")
    lines.append("")

    # --- CORE RULES (simplified) ---
    lines.append("TOOL USAGE:")
    lines.append("- Always use tools when they can help. Never pretend to do actions yourself.")
    lines.append("- ONE tool call = ONE item/device. For N items, make N separate <tool_call> blocks.")
    lines.append("- When calling tools, output ONLY <tool_call> blocks, no other text.")
    lines.append("- For general questions with no tool, use <RESPONSE>...</RESPONSE>.")
    lines.append("")

    # --- DEVICE CONTROL (simplified) ---
    lines.append("DEVICE CONTROL:")
    lines.append("1. If user provides entity_id (e.g., 'light.kitchen'), call call_service directly.")
    lines.append("2. If user uses natural names (e.g., 'kitchen light'):")
    lines.append("   a) Call list_entities with domain (usually 'light' or 'switch')")
    lines.append("   b) Match friendly_name to user's text")
    lines.append("   c) Call call_service once per matched entity")
    lines.append("3. Use describe_service if unsure about service parameters.")
    lines.append("")

    # --- EXAMPLES ---
    lines.append("# EXAMPLES")
    lines.append("")
    
    # Shopping - single item
    lines.append("User: add cheese")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "cheese"}}')
    lines.append("</tool_call>")
    lines.append("")
    
    # Shopping - multiple items (key example)
    lines.append("User: add cheese and wine")
    lines.append("# WRONG:")
    lines.append('# {"name": "shopping_add_item", "arguments": {"item": "cheese and wine"}}')
    lines.append("# CORRECT:")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "cheese"}}')
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "wine"}}')
    lines.append("</tool_call>")
    lines.append("")
    
    # Device control - known entity_ids
    lines.append("User: turn on living room and kitchen lights")
    lines.append("<tool_call>")
    lines.append('{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", "entity_id": "light.living_room"}}')
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append('{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", "entity_id": "light.kitchen"}}')
    lines.append("</tool_call>")
    lines.append("")
    
    # Device control - natural names (full flow)
    lines.append("User: Schalte Regallampe und Schranklampe an")
    lines.append("# Step 1: Find entities")
    lines.append("<tool_call>")
    lines.append('{"name": "list_entities", "arguments": {"domain": "light"}}')
    lines.append("</tool_call>")
    lines.append("# Step 2: Control each matched light")
    lines.append("<tool_call>")
    lines.append('{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", "entity_id": "light.regallampe"}}')
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append('{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", "entity_id": "light.schranklampe"}}')
    lines.append("</tool_call>")
    lines.append("")
    
    # Calendar
    lines.append("User: what's on my calendar tomorrow?")
    lines.append("<tool_call>")
    lines.append('{"name": "calendar_list_events", "arguments": {"day": "tomorrow"}}')
    lines.append("</tool_call>")
    lines.append("")
    
    # Natural language response
    lines.append("User: what day is it?")
    lines.append("<RESPONSE>")
    lines.append(f"Today is {now.strftime('%A')}.")
    lines.append("</RESPONSE>")
    lines.append("")
    
    # Date interpretation example
    lines.append("User: What's planned for April 29th?")
    lines.append("# Use current year from timestamp above")
    lines.append("<tool_call>")
    lines.append(f'{{"name": "calendar_list_events", "arguments": {{"start_date": "{now.year}-04-29", "end_date": "{now.year}-04-29"}}}}')
    lines.append("</tool_call>")
    lines.append("")

    return "\n".join(lines)