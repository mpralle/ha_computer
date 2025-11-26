"""5-Agent conversation pipeline for Llama.cpp Assist integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import ulid

from .llm_client import LlamaCppClient
from .agent_planner import PlannerAgent
from .agent_resolver import TaskResolver
from .agent_selector import SelectionAgent
from .agent_executor import TaskExecutor
from .agent_summariser import SummariserAgent

from .const import (
    CONF_API_KEY,
    CONF_ENABLE_MULTI_AGENT,
    CONF_MAX_TOKENS,
    CONF_PLANNER_URL,
    CONF_SELECTOR_URL,
    CONF_SERVER_URL,
    CONF_SUMMARISER_URL,
    CONF_TEMPERATURE,
    CONF_TIMEOUT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MultiAgentConversationEntity(conversation.AbstractConversationAgent):
    """Multi-agent conversation entity using 5-agent pipeline."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the agent."""
        self.hass = hass
        self.entry = entry

        # Get configuration
        config = entry.data
        options = entry.options

        main_server_url = config[CONF_SERVER_URL]
        api_key = config.get(CONF_API_KEY)
        
        session = async_get_clientsession(hass)
        
        # Create LLM clients for each agent (with optional per-agent URLs)
        planner_url = options.get(CONF_PLANNER_URL) or main_server_url
        selector_url = options.get(CONF_SELECTOR_URL) or main_server_url
        summariser_url = options.get(CONF_SUMMARISER_URL) or main_server_url
        
        self.planner_client = LlamaCppClient(planner_url, api_key, session)
        self.selector_client = LlamaCppClient(selector_url, api_key, session)
        self.summariser_client = LlamaCppClient(summariser_url, api_key, session)
        
        _LOGGER.info(
            "Initialized multi-agent pipeline - Planner: %s, Selector: %s, Summariser: %s",
            planner_url,
            selector_url,
            summariser_url,
        )

    @property
    def attribution(self) -> dict[str, Any]:
        """Return attribution."""
        return {
            "name": "Llama.cpp Assist (Multi-Agent)",
            "url": "https://github.com/ggerganov/llama.cpp",
        }

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages."""
        return ["en", "de"]

    @property
    def id(self) -> str:
        """Return the agent ID."""
        return self.entry.entry_id

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process user input through 5-agent pipeline OR return conversational response."""
        _LOGGER.info("Processing: %s", user_input.text)

        try:
            # 1. PLAN (using planner-specific client)
            planner = PlannerAgent(self.planner_client)
            result = await planner.plan(user_input.text, datetime.now().isoformat())

            # Check if it's a conversational response or tasks
            if "response" in result:
                # Direct conversational response
                _LOGGER.info("Planner returned conversational response")
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_speech(result["response"])
                return conversation.ConversationResult(
                    conversation_id=user_input.conversation_id or ulid.ulid_now(),
                    response=intent_response,
                )

            # Otherwise, execute tasks
            tasks = result.get("tasks", [])

            if not tasks:
                # No tasks and no response - fallback
                _LOGGER.warning("Planner returned neither tasks nor response")
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_speech("I'm not sure how to help with that.")
                return conversation.ConversationResult(
                    conversation_id=user_input.conversation_id or ulid.ulid_now(),
                    response=intent_response,
                )

            _LOGGER.info("Planner created %d task(s)", len(tasks))

            # 2. RESOLVE (provide available entities and options)
            resolver = TaskResolver(self.hass)
            resolved_tasks = await resolver.resolve_tasks(tasks)
            _LOGGER.info("Resolver processed %d task(s)", len(resolved_tasks))

            # 3. SELECT (LLM chooses specific entities - using selector-specific client)
            selector = SelectionAgent(self.selector_client)
            concrete_tasks = await selector.select(resolved_tasks)
            _LOGGER.info("Selector processed %d task(s)", len(concrete_tasks))

            # 4. EXECUTE
            executor = TaskExecutor(self.hass)
            execution_report = await executor.execute_tasks(concrete_tasks)
            _LOGGER.info(
                "Executor: %d successful, %d failed",
                execution_report.get("successful_operations", 0),
                execution_report.get("failed_operations", 0),
            )

            # 5. SUMMARISE (using summariser-specific client)
            summariser = SummariserAgent(self.summariser_client)
            response_text = await summariser.summarise(user_input.text, execution_report)

            # Return result
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(response_text)

            return conversation.ConversationResult(
                conversation_id=user_input.conversation_id or ulid.ulid_now(),
                response=intent_response,
            )

        except Exception as err:
            _LOGGER.error("Error in multi-agent pipeline: %s", err, exc_info=True)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_speech(
                "I'm sorry, I encountered an error processing your request."
            )
            return conversation.ConversationResult(
                conversation_id=user_input.conversation_id or ulid.ulid_now(),
                response=intent_response,
            )
