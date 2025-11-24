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
from .system_prompt import generate_hermes_system_prompt
from .tools import create_tool_registry
from .shopping_list_api import (
    ShoppingAddItemTool,
    ShoppingListAllTool,
    ShoppingRemoveItemTool,
)
from .calendar_api import CalendarCreateEventTool, CalendarListEventsTool

_LOGGER = logging.getLogger(__name__)


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
        
        # Get tool schemas
        tool_schemas = self.tool_registry.get_all_schemas()
        
        
        # Generate system prompt
        system_prompt = generate_hermes_system_prompt(
            self.hass,
            self.memory,
            custom_prefix=system_prompt_prefix,
            max_entities=50,
            tool_schemas=tool_schemas,
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
        use_tools = True  # Try with tools first
        
        while iteration < max_iterations:
            iteration += 1
            
            # Prepare request payload
            payload = {
                "messages": current_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            # Add tools if supported
            if use_tools and tool_schemas:
                payload["tools"] = tool_schemas
            
            _LOGGER.debug("Calling llama.cpp (iteration %d, tools=%s): %s", iteration, use_tools, server_url)
            
            # Make request
            try:
                async with asyncio.timeout(timeout):
                    async with session.post(
                        f"{server_url.rstrip('/')}/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            
                            # Check if error is related to tools not being supported
                            if use_tools and ("tools param requires" in error_text.lower() or 
                                            "unknown method" in error_text.lower() or
                                            "jinja" in error_text.lower()):
                                _LOGGER.warning(
                                    "llama.cpp server doesn't support tools properly. "
                                    "Falling back to basic conversation mode. "
                                    "Update llama.cpp or use a model with tool support for device control."
                                )
                                use_tools = False
                                iteration = 0  # Reset iteration counter
                                current_messages = messages.copy()  # Reset messages
                                continue  # Retry without tools
                            
                            raise ValueError(f"Server returned status {response.status}: {error_text}")
                        
                        data = await response.json()
            except asyncio.TimeoutError:
                raise
            except Exception as err:
                _LOGGER.error("Error calling llama.cpp: %s", err)
                raise
            
            # Extract response
            if "choices" not in data or not data["choices"]:
                raise ValueError("Invalid response: no choices")
            
            choice = data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            # Ensure content is a string
            if content is None:
                content = ""
            elif not isinstance(content, str):
                content = str(content)
            
            # Check for OpenAI-style tool calls first
            tool_calls = message.get("tool_calls", [])
            
            # If no OpenAI tool calls, try parsing text-based tool calls
            if not tool_calls and content:
                tool_calls = self._parse_text_tool_calls(content)
                if tool_calls:
                    _LOGGER.debug("Parsed %d text-based tool calls", len(tool_calls))
            
            if not tool_calls:
                # No tool calls, return the response
                # Extract just the RESPONSE section if present
                if "<RESPONSE>" in content and "</RESPONSE>" in content:
                    start = content.index("<RESPONSE>") + len("<RESPONSE>")
                    end = content.index("</RESPONSE>")
                    return content[start:end].strip()
                return content or "I don't have a response."
            
            # Add assistant message to history (ensure content is not empty)
            if content.strip():
                current_messages.append({"role": "assistant", "content": content})
            else:
                # If assistant didn't provide text, just note the tool call
                current_messages.append({"role": "assistant", "content": "Using tools to help with your request..."})
            
            # Execute tool calls
            _LOGGER.debug("Executing %d tool calls", len(tool_calls))
            
            tool_results = []
            for tool_call in tool_calls:
                if isinstance(tool_call, dict) and "function" in tool_call:
                    # OpenAI-style tool call
                    tool_name = tool_call["function"]["name"]
                    tool_args_str = tool_call["function"]["arguments"]
                    
                    try:
                        tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                    except json.JSONDecodeError:
                        tool_args = {}
                else:
                    # Text-based tool call
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("arguments", {})
                
                _LOGGER.debug("Tool call: %s(%s)", tool_name, tool_args)
                
                # Execute tool
                tool = self.tool_registry.get(tool_name)
                if tool:
                    try:
                        result = await tool.async_call(**tool_args)
                        result_str = json.dumps(result)
                        tool_results.append(f"{tool_name}: {result_str}")
                    except Exception as err:
                        _LOGGER.error("Tool execution failed: %s", err)
                        result_str = json.dumps({
                            "success": False,
                            "error": str(err),
                        })
                        tool_results.append(f"{tool_name}: {result_str}")
                else:
                    _LOGGER.error("Tool not found: %s", tool_name)
                    result_str = json.dumps({
                        "success": False,
                        "error": f"Tool {tool_name} not found",
                    })
                    tool_results.append(f"{tool_name}: {result_str}")
            
            # Add tool results to messages - ensure it's a proper string
            results_text = "Tool results:\n" + "\n".join(tool_results)
            current_messages.append({
                "role": "user",
                "content": results_text,
            })
            
            _LOGGER.debug("Tool results added to conversation: %s", results_text[:200])
            
            # Continue loop to get final response
        
        # Max iterations reached
        return "I'm sorry, I couldn't complete the task after multiple attempts."

    def _parse_text_tool_calls(self, content: str) -> list[dict[str, Any]]:
        """Parse text-based tool calls from LLM response.
        
        Supports multiple formats:
        1. <tool_call>{"name": "function_name", "arguments": {...}}</tool_call> (Hermes-3)
        2. <TOOL_CALL>tool_name(arg1="value1")</TOOL_CALL>
        3. ```homeassistant\n{"service": "light.turn_off", "target_device": "light.kitchen"}\n```
        4. ```python\n{"service": "light.turn_off", "target_device": "light.kitchen"}\n```
        """
        import re
        
        tool_calls = []
        
        _LOGGER.debug("Parsing response for tool calls. Content length: %d chars", len(content))
        _LOGGER.debug("Response content: %s", content[:500])  # First 500 chars for debugging
        
        # Format 1: Hermes-3 <tool_call> blocks (lowercase with JSON)
        hermes_pattern = r"<tool_call>(.*?)</tool_call>"
        hermes_matches = re.findall(hermes_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if hermes_matches:
            _LOGGER.debug("Found %d Hermes <tool_call> blocks", len(hermes_matches))
            for match in hermes_matches:
                match = match.strip()
                _LOGGER.debug("Parsing Hermes tool call: %s", match)
                
                try:
                    # Parse as JSON
                    data = json.loads(match)
                    tool_name = data.get("name")
                    arguments = data.get("arguments", {})
                    
                    if not tool_name:
                        _LOGGER.warning("Hermes tool call missing 'name' field: %s", match)
                        continue
                    
                    tool_calls.append({
                        "name": tool_name,
                        "arguments": arguments,
                    })
                    
                    _LOGGER.info("Parsed Hermes format: %s with args %s", tool_name, arguments)
                    
                except json.JSONDecodeError as err:
                    _LOGGER.warning("Failed to parse Hermes tool call as JSON: %s. Error: %s", match, err)
                    continue
        
        # Format 2: <TOOL_CALL> blocks (uppercase with function call syntax)
        pattern = r"<TOOL_CALL>(.*?)</TOOL_CALL>"
        matches = re.findall(pattern, content, re.DOTALL)
        
        if matches:
            _LOGGER.debug("Found %d <TOOL_CALL> blocks", len(matches))
            for match in matches:
                match = match.strip()
                
                # Parse tool_name(arg1=value1, arg2=value2)
                tool_match = re.match(r"(\w+)\((.*)\)", match, re.DOTALL)
                if not tool_match:
                    _LOGGER.warning("Could not parse tool call: %s", match)
                    continue
                
                tool_name = tool_match.group(1)
                args_str = tool_match.group(2).strip()
                
                # Parse arguments
                arguments = {}
                if args_str:
                    arg_pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,\s]+))'
                    for arg_match in re.finditer(arg_pattern, args_str):
                        key = arg_match.group(1)
                        value = arg_match.group(2) or arg_match.group(3) or arg_match.group(4)
                        
                        if value and (value.startswith("{") or value.startswith("[")):
                            try:
                                value = json.loads(value)
                            except:
                                pass
                        
                        arguments[key] = value
                
                tool_calls.append({
                    "name": tool_name,
                    "arguments": arguments,
                })
                
                _LOGGER.info("Parsed <TOOL_CALL> format: %s with args %s", tool_name, arguments)
        
        # Format 2 & 3: Markdown code blocks (```homeassistant, ```python, ```json)
        code_block_pattern = r"```(?:homeassistant|python|json)\s*\n(.*?)\n```"
        code_matches = re.findall(code_block_pattern, content, re.DOTALL)
        
        if code_matches:
            _LOGGER.debug("Found %d markdown code blocks", len(code_matches))
            for code_block in code_matches:
                code_block = code_block.strip()
                _LOGGER.debug("Parsing code block: %s", code_block)
                
                try:
                    # Try to parse as JSON
                    data = json.loads(code_block)
                    
                    # Extract service and target_device
                    service = data.get("service", "")
                    target_device = data.get("target_device", "")
                    
                    if not service:
                        _LOGGER.warning("Code block missing 'service' field: %s", code_block)
                        continue
                    
                    # Parse service into domain and service name
                    if "." in service:
                        domain, service_name = service.split(".", 1)
                    else:
                        _LOGGER.warning("Invalid service format (should be domain.service): %s", service)
                        continue
                    
                    # Build call_service arguments
                    arguments = {
                        "domain": domain,
                        "service": service_name,
                    }
                    
                    if target_device:
                        arguments["entity_id"] = target_device
                    
                    # Add any extra data fields
                    extra_data = {k: v for k, v in data.items() if k not in ["service", "target_device"]}
                    if extra_data:
                        arguments["data"] = extra_data
                    
                    tool_calls.append({
                        "name": "call_service",
                        "arguments": arguments,
                    })
                    
                    _LOGGER.info("Parsed code block format: call_service with args %s", arguments)
                    
                except json.JSONDecodeError as err:
                    _LOGGER.warning("Failed to parse code block as JSON: %s. Error: %s", code_block, err)
                    continue
        
        if not tool_calls:
            _LOGGER.debug("No tool calls found in response")
        else:
            _LOGGER.info("Total tool calls parsed: %d", len(tool_calls))
        
        return tool_calls
