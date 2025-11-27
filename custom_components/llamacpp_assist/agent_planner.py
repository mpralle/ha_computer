"""Planner Agent: Converts user utterances to structured tasks or conversational responses."""
from __future__ import annotations

import logging
from typing import Any

from .llm_client import LlamaCppClient

_LOGGER = logging.getLogger(__name__)

# System prompt for the Planner Agent
PLANNER_SYSTEM_PROMPT = """You are a smart home assistant. Analyze user requests and decide:

1. If the request is ACTIONABLE (device control, shopping list, calendar, memory), output tasks as JSON
2. If the request is CONVERSATIONAL (questions, greetings, general chat), respond directly

TASK TYPES:
- device_control: Control lights, switches, etc.
  Fields: action (turn_on/turn_off/toggle/set), raw_targets (list of names as user said them), domain (optional), params (optional)

- timer_start: Start a new timer
  Fields: duration (string like "5 minutes", "1 hour"), name (optional timer name)

- shopping_add: Add items to shopping list
  Fields: raw_items (string, keep exactly as user said it)

- shopping_query: List shopping list items
  Fields: none

- shopping_remove: Remove item from shopping list  
  Fields: item (string)

- calendar_query: Query calendar events
  Fields: start (optional), end (optional), query (optional filter text)

- calendar_create: Create calendar event
  Fields: summary, start, end, description (optional), location (optional)

- memory_read: Read from memory
  Fields: key

- memory_write: Write to memory
  Fields: key, value

VALID HOME ASSISTANT DOMAINS:
- light: Lights (Lampe, Licht, Light)
- switch: Switches, Plugs (Steckdose, Schalter)
- climate: Thermostats, HVAC (Thermostat, Heizung)
- media_player: Music, TV, Speakers (Musikanlage, Fernseher, Lautsprecher)
- cover: Blinds, Curtains (Jalousie, Rollo, Vorhang)
- lock: Door locks (Schloss, Türschloss)
- fan: Fans (Lüfter, Ventilator)
- vacuum: Vacuum cleaners (Staubsauger)
- timer: Timers (Timer, Countdown, Stoppuhr)
- sensor: Sensors (only for reading, not controlling)
- binary_sensor: Binary sensors (only for reading, not controlling)

IMPORTANT: Only use these exact domain names! Do NOT invent domains like "audio", "music", "heating" - use the correct ones from the list above.

RULES FOR TASKS:
1. Output: {{"tasks": [...]}}
2. Keep raw_targets and raw_items exactly as the user said them
3. Do NOT invent entity_ids or specific HA names
4. If user says "X und Y", put both in raw_targets (e.g., ["X", "Y"])
5. For shopping: keep raw_items as single string (splitting happens later)
6. Separate different task types (e.g., lights + shopping = 2 tasks)
7. Use domain only if obvious (Lampe → light, Steckdose → switch)
8. Always include an "id" field for each task (e.g., "t1", "t2")

RULES FOR CONVERSATIONAL:
1. Output: {{"response": "Your answer here"}}
2. Answer in the same language as the user
3. Be brief and helpful

EXAMPLES:

User: "Schalte Regallampe und Schranklampe an"
Output: {{"tasks": [{{"id": "t1", "type": "device_control", "action": "turn_on", "raw_targets": ["Regallampe", "Schranklampe"], "domain": "light"}}]}}

User: "Packe Käse und Wein auf die Einkaufsliste"
Output: {{"tasks": [{{"id": "t1", "type": "shopping_add", "raw_items": "Käse und Wein"}}]}}

User: "Turn on kitchen light and add milk to shopping list"
Output: {{"tasks": [{{"id": "t1", "type": "device_control", "action": "turn_on", "raw_targets": ["kitchen light"], "domain": "light"}}, {{"id": "t2", "type": "shopping_add", "raw_items": "milk"}}]}}

User: "Was steht morgen im Kalender?"
Output: {{"tasks": [{{"id": "t1", "type": "calendar_query", "start": "tomorrow"}}]}}

User: "Guten Morgen"
Output: {{"response": "Guten Morgen! Wie kann ich dir helfen?"}}

User: "What can you do?"
Output: {{"response": "I can help you control devices like lights and switches, manage your shopping list, check your calendar, and remember information for you. Just ask!"}}

Current date: {current_date}"""


class PlannerAgent:
    """
    Agent that converts user utterances into structured tasks or provides conversational responses.
    
    This is the first agent in the pipeline. It determines whether the user request
    is actionable (requires tasks) or conversational (direct response).
    """
    
    def __init__(self, llm_client: LlamaCppClient) -> None:
        """Initialize the Planner Agent."""
        self.llm_client = llm_client
    
    async def plan(
        self,
        user_utterance: str,
        current_date: str,
    ) -> dict[str, Any]:
        """
        Convert user utterance to tasks or conversational response.
        
        Args:
            user_utterance: The user's input text
            current_date: Current date/time in ISO format
        
        Returns:
            Either {"tasks": [...]} or {"response": "..."}
        
        Raises:
            ValueError: If LLM response is invalid
        """
        system_prompt = PLANNER_SYSTEM_PROMPT.format(current_date=current_date)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_utterance},
        ]
        
        _LOGGER.debug("Planner processing: %s", user_utterance)
        
        try:
            result = await self.llm_client.parse_json_response(
                messages,
                temperature=0.1,
                max_tokens=500,
                timeout=30,
            )
        except Exception as err:
            _LOGGER.error("Planner failed to parse LLM response: %s", err)
            # Fallback to conversational response
            return {
                "response": "I'm sorry, I had trouble understanding that. Could you rephrase?"
            }
        
        # Validate response structure
        if "tasks" in result:
            tasks = result["tasks"]
            if not isinstance(tasks, list):
                _LOGGER.error("Planner returned invalid tasks format: %s", tasks)
                return {
                    "response": "I'm sorry, I had trouble processing that request."
                }
            
            # Ensure each task has an id
            for i, task in enumerate(tasks):
                if "id" not in task:
                    task["id"] = f"t{i+1}"
                if "status" not in task:
                    task["status"] = "pending"
            
            _LOGGER.info("Planner created %d task(s)", len(tasks))
            return {"tasks": tasks}
        
        elif "response" in result:
            _LOGGER.info("Planner provided conversational response")
            return {"response": result["response"]}
        
        else:
            _LOGGER.error("Planner returned neither tasks nor response: %s", result)
            return {
                "response": "I'm not sure how to help with that."
            }
