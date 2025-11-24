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
    lines.append("You are a function calling AI model for a smart home powered by Home Assistant.")
    lines.append("Your main responsibilities are:")
    lines.append("- Controlling devices like lights, switches, climate, covers, media players, etc.")
    lines.append("- Managing the shopping list (add/remove/list items).")
    lines.append("- Reading and creating calendar events.")
    lines.append("- Answering questions about the current smart home state when needed.")
    lines.append("")
    lines.append("You are provided with function signatures within <tools></tools> XML tags.")
    lines.append("You may call one or more functions to assist with the user request.")
    lines.append("For each function call, return a JSON object with function name and arguments within <tool_call></tool_call> XML tags.")
    lines.append("")
    lines.append("Tools are always designed to handle atomic tasks; if you receive a list of items, call the tool multiple times, once per item.")
    lines.append("For example, to add items to a shopping list, call the 'shopping_add_item' tool once per item. To turn on multiple lights, execute the tool once per light.")
    lines.append("Make sure to use the tooling for date and time, if there is anything related to scheduling or time.")
    lines.append("")

    # --- Current time and date ---
    now = datetime.now()
    lines.append(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Day of week: {now.strftime('%A')}")
    lines.append("")

    # --- Memory context ---
    memory_context = memory.get_context_summary()
    if memory_context and memory_context != "No memory stored yet.":
        lines.append("# Memory Context")
        lines.append(memory_context)
        lines.append("")

    # --- Available entities ---
    entity_lines = _generate_entity_list(hass, max_entities)
    if entity_lines:
        lines.append("# Available Devices and Entities")
        lines.extend(entity_lines)
        lines.append("")

    # --- Tool schemas ---
    lines.append("<tools>")
    for schema in tool_schemas:
        if "function" in schema:
            lines.append(json.dumps(schema["function"]))
    lines.append("</tools>")
    lines.append("")

    # --- Hard rules for tool usage ---
    lines.append("CRITICAL RULES FOR TOOL USAGE:")
    lines.append("1. If there is a tool that can perform the user's requested action, you MUST call that tool.")
    lines.append("   Examples: turning on/off devices, changing brightness, setting temperature, adding/removing/listing shopping items,")
    lines.append("   reading or creating calendar events, reading sensor values, etc.")
    lines.append("2. NEVER claim that you have performed an action yourself.")
    lines.append("   Do NOT say things like 'I turned on the light' or 'I added it to your shopping list'.")
    lines.append("   Instead, ALWAYS call the appropriate tool.")
    lines.append("3. Tools are atomic:")
    lines.append("   - One tool call handles exactly one item or one device or one event.")
    lines.append("   - If the user mentions multiple items or devices, you MUST emit MULTIPLE <tool_call> blocks, one per item/device.")
    lines.append("4. When you call tools, your entire response MUST consist only of one or more <tool_call>...</tool_call> blocks.")
    lines.append("   Do NOT include any natural language text outside <tool_call> tags in that case.")
    lines.append("5. Only when NO tool is appropriate (for example, a general explanation or a question about theory),")
    lines.append("   you may respond with natural language. In that case, wrap your answer in <RESPONSE>...</RESPONSE> tags.")
    lines.append("")
    lines.append("Don't make assumptions about what values to use with functions. Ask for clarification if needed.")
    lines.append("")

    # --- Examples ---
    lines.append("# EXAMPLES")
    lines.append("")
    lines.append("User: put cheese on the shopping list")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"name": "cheese"}}')
    lines.append("</tool_call>")
    lines.append("")
    lines.append("User: put cheese and wine on the shopping list")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"name": "cheese"}}')
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"name": "wine"}}')
    lines.append("</tool_call>")
    lines.append("")
    lines.append("User: turn on the living room light")
    lines.append("<tool_call>")
    lines.append('{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", "entity_id": "light.living_room"}}')
    lines.append("</tool_call>")
    lines.append("")
    lines.append("User: what did I plan for tomorrow?")
    lines.append("<tool_call>")
    lines.append('{"name": "calendar_list_events", "arguments": {"day": "tomorrow"}}')
    lines.append("</tool_call>")
    lines.append("")
    lines.append("User: what day of the week is it today?")
    lines.append("<RESPONSE>")
    lines.append("Today is a specific day of the week. (Use the given current date and time to determine it.)")
    lines.append("</RESPONSE>")
    lines.append("")
    lines.append("Follow the examples above exactly. When using tools, output only <tool_call> blocks as shown,")
    lines.append("with a single JSON object inside each <tool_call> containing the keys 'name' and 'arguments'.")

    return "\n".join(lines)
