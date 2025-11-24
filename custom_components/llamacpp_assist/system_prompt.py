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
    """Generate system prompt in Hermes-3 format with tool definitions."""
    import json
    
    lines = []
    
    # Custom prefix if provided
    if custom_prefix:
        lines.append(custom_prefix)
        lines.append("")
    
    lines.append("You are a function calling AI model for a smart home powered by Home Assistant.")
    lines.append("You are provided with function signatures within <tools></tools> XML tags.")
    lines.append("You may call one or more functions to assist with the user request.")
    lines.append("For each function call, return a JSON object with function name and arguments within <tool_call></tool_call> XML tags.")
    lines.append("Tools are always designed to handle atomic tasks; if you receive a list of items, call the tool multiple times, once per item.")
    lines.append("For example, to add items to a shopping list, call the 'shopping_add_item' tool once per item. To turn on multiple lights, execute the tool once per light.")
    lines.append("Make sure to use the tooling for date and time, if there is anything related to scheduling or time.")
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
    
    # Add tool schemas
    lines.append("<tools>")
    for schema in tool_schemas:
        if "function" in schema:
            lines.append(json.dumps(schema["function"]))
    lines.append("</tools>")
    lines.append("")
    lines.append("Don't make assumptions about what values to use with functions. Ask for clarification if needed.")
    lines.append("When you decide to call a tool, respond with ONLY a single <tool_call>...</tool_call> block.")
    lines.append("Inside <tool_call>, output a single JSON object with keys 'name' and 'arguments', and nothing else.")
    lines.append("Do NOT add explanations, natural language, or extra text outside <tool_call> when calling tools.")


    
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
        entities_by_domain: dict[str, list[tuple[str, str, str, str]]] = {}
        
        for state in states:
            entity_id = state.entity_id
            domain = entity_id.split(".")[0]
            
            # Skip certain domains but INCLUDE sensors for temperature, etc.
            if domain in ["group", "zone", "automation", "script", "update", "binary_sensor"]:
                continue
            
            # Get friendly name
            friendly_name = state.attributes.get("friendly_name", entity_id)
            
            # Get current state
            current_state = state.state
            
            # Get area
            entity_entry = ent_reg.async_get(entity_id)
            area_name = ""
            if entity_entry and entity_entry.area_id:
                area_entry = area_reg.async_get_area(entity_entry.area_id)
                if area_entry:
                    area_name = area_entry.name
            
            if domain not in entities_by_domain:
                entities_by_domain[domain] = []
            
            entities_by_domain[domain].append((entity_id, friendly_name, area_name, current_state))
        
        # Sort and limit - prioritize important domains
        priority_domains = ["light", "switch", "climate", "media_player", "cover", "fan"]
        total_count = 0
        
        # Show priority domains first
        for domain in priority_domains:
            if domain in entities_by_domain and total_count < max_entities:
                entities = entities_by_domain[domain][:15]  # Max 15 per domain
                
                lines.append(f"\n**{domain.title()}:**")
                for entity_id, friendly_name, area_name, current_state in entities:
                    area_text = f" [{area_name}]" if area_name else ""
                    state_text = f" (currently: {current_state})" if current_state not in ["unknown", "unavailable"] else ""
                    lines.append(f"- **{friendly_name}**{area_text}: `{entity_id}`{state_text}")
                    total_count += 1
                    
                    if total_count >= max_entities:
                        break
        
        # Show other domains
        for domain in sorted(entities_by_domain.keys()):
            if domain in priority_domains or total_count >= max_entities:
                continue
            
            entities = entities_by_domain[domain][:10]  # Max 10 for other domains
            
            lines.append(f"\n**{domain.title()}:**")
            for entity_id, friendly_name, area_name, current_state in entities:
                area_text = f" [{area_name}]" if area_name else ""
                state_text = f" (currently: {current_state})" if current_state not in ["unknown", "unavailable"] else ""
                lines.append(f"- **{friendly_name}**{area_text}: `{entity_id}`{state_text}")
                total_count += 1
                
                if total_count >= max_entities:
                    break
        
        if total_count >= max_entities:
            lines.append(f"\n_(Showing {total_count} of {sum(len(e) for e in entities_by_domain.values())} total entities)_")
        
        # Add helpful note
        lines.append("\n**Important:** Use the exact `entity_id` (in backticks) when calling services, not the friendly name.")
    
    except Exception as err:
        _LOGGER.error("Failed to generate entity list: %s", err)
        lines.append("(Unable to load entity list)")
    
    return lines
