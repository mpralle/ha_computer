"""Config flow for Llama.cpp Assist integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_MAX_TOKENS,
    CONF_MODEL_NAME,
    CONF_SERVER_URL,
    CONF_SYSTEM_PROMPT_PREFIX,
    CONF_TEMPERATURE,
    CONF_TIMEOUT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_NAME,
    DEFAULT_SERVER_URL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def validate_server_connection(
    hass: HomeAssistant, server_url: str, api_key: str | None, timeout: int
) -> dict[str, Any]:
    """Validate the server connection by making a test request."""
    session = async_get_clientsession(hass)
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # Test with a simple completion request
    test_payload = {
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 10,
    }
    
    try:
        async with asyncio.timeout(timeout):
            async with session.post(
                f"{server_url.rstrip('/')}/v1/chat/completions",
                json=test_payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Server returned status {response.status}")
                
                data = await response.json()
                
                # Validate response structure
                if "choices" not in data:
                    raise ValueError("Invalid response format")
                
                return {"success": True}
                
    except asyncio.TimeoutError:
        raise ValueError("timeout")
    except aiohttp.ClientError as err:
        _LOGGER.error("Connection error: %s", err)
        raise ValueError("cannot_connect")
    except Exception as err:
        _LOGGER.error("Validation error: %s", err)
        raise ValueError("invalid_response")


class LlamaCppAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Llama.cpp Assist."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(user_input[CONF_SERVER_URL])
            self._abort_if_unique_id_configured()

            # Validate server connection
            try:
                await validate_server_connection(
                    self.hass,
                    user_input[CONF_SERVER_URL],
                    user_input.get(CONF_API_KEY),
                    user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                )
            except ValueError as err:
                errors["base"] = str(err)
            else:
                # Create the entry
                return self.async_create_entry(
                    title=user_input.get(CONF_MODEL_NAME, "Llama.cpp Assist"),
                    data=user_input,
                )

        # Show the form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_SERVER_URL, default=DEFAULT_SERVER_URL): str,
                vol.Optional(CONF_API_KEY): str,
                vol.Optional(CONF_MODEL_NAME, default=DEFAULT_MODEL_NAME): str,
                vol.Optional(CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0, max=2.0)
                ),
                vol.Optional(CONF_MAX_TOKENS, default=DEFAULT_MAX_TOKENS): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=4096)
                ),
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=120)
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LlamaCppAssistOptionsFlow:
        """Get the options flow for this handler."""
        return LlamaCppAssistOptionsFlow(config_entry)


class LlamaCppAssistOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Llama.cpp Assist."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values from config or options
        current_temp = self.config_entry.options.get(
            CONF_TEMPERATURE,
            self.config_entry.data.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
        )
        current_max_tokens = self.config_entry.options.get(
            CONF_MAX_TOKENS,
            self.config_entry.data.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
        )
        current_timeout = self.config_entry.options.get(
            CONF_TIMEOUT,
            self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )
        current_prompt_prefix = self.config_entry.options.get(
            CONF_SYSTEM_PROMPT_PREFIX, ""
        )

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_TEMPERATURE, default=current_temp): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0, max=2.0)
                ),
                vol.Optional(CONF_MAX_TOKENS, default=current_max_tokens): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=4096)
                ),
                vol.Optional(CONF_TIMEOUT, default=current_timeout): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=120)
                ),
                vol.Optional(
                    CONF_SYSTEM_PROMPT_PREFIX, default=current_prompt_prefix
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
