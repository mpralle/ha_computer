"""Conversation agent for Llama.cpp Assist integration."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import ulid

from .const import (
    CONF_API_KEY,
    CONF_MAX_TOKENS,
    CONF_SERVER_URL,
    CONF_SYSTEM_PROMPT_PREFIX,
    CONF_TEMPERATURE,
    CONF_TIMEOUT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .system_prompt import generate_system_prompt
from .tools import create_tool_registry
from .shopping_list_api import (
    ShoppingAddItemTool,
    ShoppingListAllTool,
    ShoppingRemoveItemTool,
)
from .calendar_api import CalendarCreateEventTool, CalendarListEventsTool

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Llama.cpp conversation agent from a config entry."""
    agent = LlamaCppConversationEntity(hass, entry)
    conversation.async_set_agent(hass, entry, agent)


class LlamaCppConversationEntity(conversation.AbstractConversationAgent):
    """Llama.cpp conversation agent."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry
        
        # Get memory storage
        self.memory = hass.data[DOMAIN][entry.entry_id]["memory"]
        
        # Create tool registry
        self.tool_registry = create_tool_registry(hass, self.memory)
        
        # Register shopping list tools
        self.tool_registry.register(ShoppingAddItemTool(hass))
        self.tool_registry.register(ShoppingRemoveItemTool(hass))
        self.tool_registry.register(ShoppingListAllTool(hass))
        
        # Register calendar tools
        self.tool_registry.register(CalendarListEventsTool(hass))
        self.tool_registry.register(CalendarCreateEventTool(hass))
        
        _LOGGER.info(
            "Initialized Llama.cpp conversation agent with %d tools",
            len(self.tool_registry.get_all_tools()),
        )

    @property
    def attribution(self) -> dict[str, Any]:
        """Return attribution."""
        return {
            "name": "Llama.cpp Assist",
            "url": "https://github.com/ggerganov/llama.cpp",
        }

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages."""
        return ["en", "de"]  # English and German supported

    @property
    def id(self) -> str:
        """Return the agent ID."""
        return self.entry.entry_id

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a user input."""
        _LOGGER.debug("Processing conversation input: %s", user_input.text)
        
        # Get configuration
        config = self.entry.data
        options = self.entry.options
        
        server_url = config[CONF_SERVER_URL]
        api_key = config.get(CONF_API_KEY)
        temperature = options.get(CONF_TEMPERATURE, config.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE))
        max_tokens = options.get(CONF_MAX_TOKENS, config.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS))
        timeout = options.get(CONF_TIMEOUT, config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
        system_prompt_prefix = options.get(CONF_SYSTEM_PROMPT_PREFIX)
        
        # Generate system prompt
        system_prompt = generate_system_prompt(
            self.hass,
            self.memory,
            custom_prefix=system_prompt_prefix,
        )
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input.text},
        ]
        
        # Add conversation history if available
        if user_input.conversation_id:
            # TODO: Load conversation history from storage
            pass
        
        # Get tool schemas
        tool_schemas = self.tool_registry.get_all_schemas()
        
        # Call LLM with tool calling loop
        try:
            response_text = await self._call_llm_with_tools(
                server_url,
                api_key,
                messages,
                tool_schemas,
                temperature,
                max_tokens,
                timeout,
            )
            
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(response_text)
            
            return conversation.ConversationResult(
                conversation_id=user_input.conversation_id or ulid.ulid_now(),
                response=intent_response,
            )
            
        except asyncio.TimeoutError:
            _LOGGER.error("Request to llama.cpp server timed out")
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                "I'm sorry, the request timed out. Please try again."
            )
            return conversation.ConversationResult(
                conversation_id=user_input.conversation_id or ulid.ulid_now(),
                response=intent_response,
            )
            
        except Exception as err:
            _LOGGER.error("Error processing conversation: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                "I'm sorry, I encountered an error processing your request."
            )
            return conversation.ConversationResult(
                conversation_id=user_input.conversation_id or ulid.ulid_now(),
                response=intent_response,
            )

    async def _call_llm_with_tools(
        self,
        server_url: str,
        api_key: str | None,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        timeout: int,
        max_iterations: int = 5,
    ) -> str:
        """Call LLM with tool calling support."""
        session = async_get_clientsession(self.hass)
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        iteration = 0
        current_messages = messages.copy()
        
        while iteration < max_iterations:
            iteration += 1
            
            # Prepare request payload
            payload = {
                "messages": current_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tool_schemas,
            }
            
            _LOGGER.debug("Calling llama.cpp (iteration %d): %s", iteration, server_url)
            
            # Make request
            async with asyncio.timeout(timeout):
                async with session.post(
                    f"{server_url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(f"Server returned status {response.status}: {error_text}")
                    
                    data = await response.json()
            
            # Extract response
            if "choices" not in data or not data["choices"]:
                raise ValueError("Invalid response: no choices")
            
            choice = data["choices"][0]
            message = choice.get("message", {})
            
            # Check for tool calls
            tool_calls = message.get("tool_calls", [])
            
            if not tool_calls:
                # No tool calls, return the response
                return message.get("content", "I don't have a response.")
            
            # Add assistant message with tool calls to history
            current_messages.append(message)
            
            # Execute tool calls
            _LOGGER.debug("Executing %d tool calls", len(tool_calls))
            
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                tool_args_str = tool_call["function"]["arguments"]
                tool_id = tool_call.get("id", "call_" + ulid.ulid_now())
                
                _LOGGER.debug("Tool call: %s(%s)", tool_name, tool_args_str)
                
                # Parse arguments
                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_args = {}
                
                # Execute tool
                tool = self.tool_registry.get(tool_name)
                if tool:
                    try:
                        result = await tool.async_call(**tool_args)
                        result_str = json.dumps(result)
                    except Exception as err:
                        _LOGGER.error("Tool execution failed: %s", err)
                        result_str = json.dumps({
                            "success": False,
                            "error": str(err),
                        })
                else:
                    _LOGGER.error("Tool not found: %s", tool_name)
                    result_str = json.dumps({
                        "success": False,
                        "error": f"Tool {tool_name} not found",
                    })
                
                # Add tool response to messages
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result_str,
                })
            
            # Continue loop to get final response
        
        # Max iterations reached
        return "I'm sorry, I couldn't complete the task after multiple attempts."
