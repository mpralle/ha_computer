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


def generate_system_prompt(
    hass: HomeAssistant,
    memory: MemoryStorage,
    custom_prefix: str | None = None,
    max_entities: int = 50,
) -> str:
    """Generate a dynamic system prompt with current context.
    
    Args:
        hass: Home Assistant instance
        memory: Memory storage instance
        custom_prefix: Optional custom text to prepend
        max_entities: Maximum number of entities to include
        
    Returns:
        Formatted system prompt string
    """
    lines = []
    
    # Custom prefix if provided
    if custom_prefix:
        lines.append(custom_prefix)
        lines.append("")
    
    # Base instructions
    lines.append("You are a helpful AI assistant for a smart home powered by Home Assistant.")
    lines.append("You can control devices, answer questions, and help with various tasks.")
    lines.append("")
    
    # Current time and date
    now = datetime.now()
    lines.append(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Day of week: {now.strftime('%A')}")
    lines.append("")
    
    # Memory context
    memory_context = memory.get_context_summary()
    if memory_context and memory_context != "No memory stored yet.":
        lines.append("# Memory Context")
        lines.append(memory_context)
        lines.append("")
    
    # Available entities
    entity_lines = _generate_entity_list(hass, max_entities)
    if entity_lines:
        lines.append("# Available Devices and Entities")
        lines.extend(entity_lines)
        lines.append("")
    
    # Tool usage instructions
    lines.append("# Available Tools")
    lines.append("You have access to the following tools to interact with the smart home:")
    lines.append("")
    lines.append("To use a tool, respond with:")
    lines.append("<TOOL_CALL>")
    lines.append("tool_name(arg1=value1, arg2=value2)")
    lines.append("</TOOL_CALL>")
    lines.append("<RESPONSE>Your message to the user</RESPONSE>")
    lines.append("")
    lines.append("You can call multiple tools in sequence. Always explain what you're doing in the RESPONSE section.")
    lines.append("")
    lines.append("**Home Assistant Control:**")
    lines.append("- `get_state(entity_id=\"light.kitchen\")`: Get current state and attributes")
    lines.append("- `list_entities(domain=\"light\", area=\"kitchen\")`: List entities (both args optional)")
    lines.append("- `call_service(domain=\"light\", service=\"turn_on\", entity_id=\"light.kitchen\", data={})`: Control devices")
    lines.append("")
    lines.append("**Memory:**")
    lines.append("- `memory_read(key=\"preferences.temperature\")`: Read from persistent memory")
    lines.append("- `memory_write(key=\"preferences.temperature\", value=\"21\")`: Store information")
    lines.append("- `memory_list_keys()`: List all stored memory keys")
    lines.append("")
    lines.append("**Shopping List:**")
    lines.append("- `shopping_add_item(item=\"milk\")`: Add item to shopping list")
    lines.append("- `shopping_remove_item(item=\"milk\")`: Remove item from shopping list")
    lines.append("- `shopping_list_all()`: Get all items on shopping list")
    lines.append("")
    lines.append("**Calendar:**")
    lines.append("- `calendar_list_events(start=\"today\", end=\"tomorrow\", calendar_entity=\"calendar.personal\")`: List events")
    lines.append("- `calendar_create_event(calendar_entity=\"calendar.personal\", title=\"Meeting\", start=\"2025-11-24T14:00:00\", end=\"2025-11-24T15:00:00\", description=\"Team sync\")`: Create event")
    lines.append("")
    lines.append("**Utilities:**")
    lines.append("- `get_time()`: Get current time")
    lines.append("- `get_date()`: Get current date")
    lines.append("- `get_datetime()`: Get current date and time")
    lines.append("")
    lines.append("# Example Tool Usage")
    lines.append("User: Turn on the kitchen light")
    lines.append("Assistant:")
    lines.append("<TOOL_CALL>")
    lines.append("call_service(domain=\"light\", service=\"turn_on\", entity_id=\"light.kitchen\")")
    lines.append("</TOOL_CALL>")
    lines.append("<RESPONSE>I've turned on the kitchen light.</RESPONSE>")
    lines.append("")
    lines.append("User: What's my favorite color?")
    lines.append("Assistant:")
    lines.append("<TOOL_CALL>")
    lines.append("memory_read(key=\"preferences.favorite_color\")")
    lines.append("</TOOL_CALL>")
    lines.append("<RESPONSE>Based on what you told me, your favorite color is blue.</RESPONSE>")
    lines.append("")
    lines.append("# Guidelines")
    lines.append("- Use tools when you need to interact with devices or retrieve information")  
    lines.append("- Always use <TOOL_CALL> and </TOOL_CALL> tags around tool usage")
    lines.append("- Always include a <RESPONSE> section for the user")
    lines.append("- Be conversational and helpful")
    lines.append("- If a request is unclear, ask for clarification (no tool call needed)")
    lines.append("- Store important user preferences in memory for future reference")
    lines.append("- Always confirm when you've completed an action")
    
    return "\n".join(lines)


def _generate_entity_list(hass: HomeAssistant, max_entities: int) -> list[str]:
    """Generate a formatted list of available entities."""
    lines = []
    
    try:
        # Get registries
        ent_reg = entity_registry.async_get(hass)
        area_reg = area_registry.async_get(hass)
        
        # Get all states
        states = hass.states.async_all()
        
        # Group entities by domain
        entities_by_domain: dict[str, list[tuple[str, str, str]]] = {}
        
        for state in states:
            entity_id = state.entity_id
            domain = entity_id.split(".")[0]
            
            # Skip certain domains
            if domain in ["group", "zone", "automation", "script", "sensor"]:
                continue
            
            # Get friendly name
            friendly_name = state.attributes.get("friendly_name", entity_id)
            
            # Get area
            entity_entry = ent_reg.async_get(entity_id)
            area_name = "Unknown"
            if entity_entry and entity_entry.area_id:
                area_entry = area_reg.async_get_area(entity_entry.area_id)
                if area_entry:
                    area_name = area_entry.name
            
            if domain not in entities_by_domain:
                entities_by_domain[domain] = []
            
            entities_by_domain[domain].append((entity_id, friendly_name, area_name))
        
        # Sort and limit
        total_count = 0
        for domain in sorted(entities_by_domain.keys()):
            entities = entities_by_domain[domain][:10]  # Max 10 per domain
            
            if total_count >= max_entities:
                break
            
            lines.append(f"\n**{domain.title()}:**")
            for entity_id, friendly_name, area_name in entities:
                lines.append(f"- {entity_id} ({friendly_name}) - {area_name}")
                total_count += 1
                
                if total_count >= max_entities:
                    break
        
        if total_count >= max_entities:
            lines.append(f"\n(Showing {total_count} of {sum(len(e) for e in entities_by_domain.values())} total entities)")
    
    except Exception as err:
        _LOGGER.error("Failed to generate entity list: %s", err)
        lines.append("(Unable to load entity list)")
    
    return lines
