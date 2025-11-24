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
    lines.append("Tools are always designed to handle ATOMIC tasks.")
    lines.append("If the user gives you a LIST of items or devices, you MUST perform MULTIPLE tool calls, one per item/device.")
    lines.append("You MUST NEVER pass multiple items or devices inside a single argument like 'cheese and wine' or 'light1, light2'.")
    lines.append("Instead, you MUST emit multiple <tool_call> blocks, one for each atomic item/device.")
    lines.append("Make sure to use the tooling for date and time, if there is anything related to scheduling or time.")
    lines.append("")

    # --- Current time and date ---
    now = datetime.now()
    lines.append(f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Day of week: {now.strftime('%A')}")
    lines.append("")

    # --- Date interpretation rules ---
    lines.append("DATE INTERPRETATION RULES:")
    lines.append(
        "Whenever the user mentions a calendar date without a year "
        "(for example '29 April' or 'on the 29th of April'), "
        "you MUST interpret it using the current year from the 'Current date and time' above, "
        "unless the user explicitly specifies another year."
    )
    lines.append("Example:")
    lines.append("  Current date and time: 2025-11-24 10:00:00")
    lines.append("  User: What do I have planned for the 29th of April?")
    lines.append("  -> Use 2025-04-29 when calling calendar tools.")
    lines.append("")

    # --- Memory context (optional, currently disabled to reduce context) ---
    # memory_context = memory.get_context_summary()
    # if memory_context and memory_context != "No memory stored yet.":
    #     lines.append("# Memory Context")
    #     lines.append(memory_context)
    #     lines.append("")

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
    lines.append(
        "   Examples: turning on/off devices, changing brightness, setting temperature, "
        "adding/removing/listing shopping items, reading or creating calendar events, "
        "reading sensor values, etc."
    )
    lines.append("2. NEVER claim that you have performed an action yourself.")
    lines.append(
        "   Do NOT say things like 'I turned on the light' or 'I added it to your shopping list'. "
        "Instead, ALWAYS call the appropriate tool."
    )
    lines.append("3. Tools are STRICTLY ATOMIC:")
    lines.append("   - ONE tool call handles exactly ONE item or ONE device or ONE event.")
    lines.append(
        "   - If the user mentions N items/devices, you MUST emit EXACTLY N <tool_call> blocks."
    )
    lines.append(
        "   - You MUST NOT put multiple items/devices inside a single argument string like "
        "'cheese and wine' or 'living room and kitchen lights'."
    )
    lines.append(
        "3b. For call_service, the 'entity_id' MUST be a single entity_id string, "
        "never a comma-separated list. To control multiple devices, call call_service "
        "multiple times, once per entity."
    )
    lines.append(
        "4. When you call tools, your entire response MUST consist only of one or more "
        "<tool_call>...</tool_call> blocks."
    )
    lines.append(
        "   Do NOT include any natural language text outside <tool_call> tags in that case."
    )
    lines.append(
        "5. Only when NO tool is appropriate (for example, a general explanation or a question "
        "about theory), you may respond with natural language. In that case, wrap your answer in "
        "<RESPONSE>...</RESPONSE> tags."
    )
    lines.append(
        "6. For the shopping_add_item tool specifically, treat the 'item' argument as a SINGLE item name. "
        "If the user text contains 'and' / 'und' or commas, you MUST split it into separate items and emit "
        "one shopping_add_item tool call per item in the SAME response."
    )
    lines.append(
        "7. If the user uses a verb like 'turn on', 'turn off', 'switch on', 'switch off', "
        "'schalte ... an', 'schalte ... aus', 'mach ... an', or 'mach ... aus', "
        "you MUST treat this as DEVICE CONTROL, not a shopping list operation. "
        "In such cases you MUST use device tools like 'call_service' and, if necessary, "
        "'list_entities', and you MUST NOT call any shopping_list_* tools."
    )
    lines.append(
        "8. When the user refers to a device by a natural-language name "
        "(e.g. 'Schrank', 'Schranklampe', 'Wohnzimmerlampe'), you MUST NOT invent entity_ids. "
        "Instead, FIRST call 'list_entities' with an appropriate domain (typically 'light' or 'switch'), "
        "and, if possible, a 'name' filter that is a substring of the friendly_name "
        "(for example name='Schrank'). Then select the matching entities by comparing the 'friendly_name' field. "
        "After that, call 'call_service' once per matched entity_id."
    )
    lines.append(
        "   Do NOT translate German names into English when matching. "
        "Always use the exact entity_ids from 'list_entities' or the '# Available Devices and Entities' section above."
    )
    lines.append(
        "9. When you need to find devices by name, you MUST NOT call list_entities with no arguments "
        "unless absolutely necessary. Prefer to pass 'domain' (e.g. 'light', 'switch') and a 'name' "
        "substring that comes from the user's wording."
    )
    lines.append("")
    lines.append("Don't make assumptions about what values to use with functions. Ask for clarification if needed.")
    lines.append("")
    lines.append(
        "If you are unsure how to call a Home Assistant service or which fields are required, "
        "FIRST call the 'describe_service' tool for that domain and service, then use the result "
        "to build a correct 'call_service' invocation."
    )

    # --- Positive & negative EXAMPLES ---
    lines.append("# EXAMPLES")
    lines.append("")
    # Simple single-item shopping
    lines.append("User: put cheese on the shopping list")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "cheese"}}')
    lines.append("</tool_call>")
    lines.append("")
    # Multi-item shopping list (2 items)
    lines.append("User: add cheese and wine to my shopping list")
    lines.append("# WRONG (do NOT do this):")
    lines.append("# <tool_call>")
    lines.append('# {"name": "shopping_add_item", "arguments": {"item": "cheese and wine"}}')
    lines.append("# </tool_call>")
    lines.append("# CORRECT (ALWAYS do this instead):")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "cheese"}}')
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "wine"}}')
    lines.append("</tool_call>")
    lines.append("")
    # Multi-item shopping list (3+ items)
    lines.append("User: add bread, milk, and eggs to my shopping list")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "bread"}}')
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "milk"}}')
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append('{"name": "shopping_add_item", "arguments": {"item": "eggs"}}')
    lines.append("</tool_call>")
    lines.append("")
    # Lights multi-device example (direct entity_ids)
    lines.append("User: turn on the living room and kitchen lights")
    lines.append("<tool_call>")
    lines.append(
        '{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", '
        '"entity_id": "light.living_room"}}'
    )
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append(
        '{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", '
        '"entity_id": "light.kitchen"}}'
    )
    lines.append("</tool_call>")
    lines.append("")
    # German device control, multiple lights via list_entities
    lines.append("User: Schalte Schrank und Schranklampe an")
    lines.append("# Correct behaviour: first discover lights, then turn on the matching ones.")
    lines.append("<tool_call>")
    lines.append(
        '{"name": "list_entities", "arguments": {"domain": "light", "name": "Schrank"}}'
    )
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append(
        '{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", '
        '"entity_id": "light.schrank"}}'
    )
    lines.append("</tool_call>")
    lines.append("<tool_call>")
    lines.append(
        '{"name": "call_service", "arguments": {"domain": "light", "service": "turn_on", '
        '"entity_id": "light.schranklampe"}}'
    )
    lines.append("</tool_call>")
    lines.append("")
    # Calendar example
    lines.append("User: what did I plan for tomorrow?")
    lines.append("<tool_call>")
    lines.append('{"name": "calendar_list_events", "arguments": {"day": "tomorrow"}}')
    lines.append("</tool_call>")
    lines.append("")
    # Pure text example
    lines.append("User: what day of the week is it today?")
    lines.append("<RESPONSE>")
    lines.append("Today is monday. (Use the given current date and time to determine it.)")
    lines.append("</RESPONSE>")
    lines.append("")
    lines.append(
        "Follow the examples above exactly. When using tools, output only <tool_call> blocks as shown, "
        "with a single JSON object inside each <tool_call> containing the keys 'name' and 'arguments'."
    )

    return "\n".join(lines)


def _generate_entity_list(hass: HomeAssistant, max_entities: int) -> list[str]:
    """Generate a formatted list of available entities."""
    lines: list[str] = []

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

            entities_by_domain[domain].append(
                (entity_id, friendly_name, area_name, current_state)
            )

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
                    state_text = (
                        f" (currently: {current_state})"
                        if current_state not in ["unknown", "unavailable"]
                        else ""
                    )
                    lines.append(
                        f"- **{friendly_name}**{area_text}: `{entity_id}`{state_text}"
                    )
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
                state_text = (
                    f" (currently: {current_state})"
                    if current_state not in ["unknown", "unavailable"]
                    else ""
                )
                lines.append(
                    f"- **{friendly_name}**{area_text}: `{entity_id}`{state_text}"
                )
                total_count += 1

                if total_count >= max_entities:
                    break

        if total_count >= max_entities:
            lines.append(
                f"\n_(Showing {total_count} of "
                f"{sum(len(e) for e in entities_by_domain.values())} total entities)_"
            )

        # Add helpful note
        lines.append(
            "\n**Important:** Use the exact `entity_id` (in backticks) when calling services, "
            "not the friendly name."
        )

    except Exception as err:
        _LOGGER.error("Failed to generate entity list: %s", err)
        lines.append("(Unable to load entity list)")

    return lines
