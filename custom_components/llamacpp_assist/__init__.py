"""The Llama.cpp Assist integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .conversation import LlamaCppConversationEntity
from .memory import MemoryStorage

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Llama.cpp Assist from a config entry."""
    _LOGGER.debug("Setting up Llama.cpp Assist integration for entry %s", entry.entry_id)
    
    # Initialize memory storage
    memory_storage = MemoryStorage(hass)
    await memory_storage.async_load()
    
    # Store in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "memory": memory_storage,
    }
    
    # Create and register conversation agent directly (not via platform)
    from homeassistant.components import conversation
    
    agent = LlamaCppConversationEntity(hass, entry)
    conversation.async_set_agent(hass, entry, agent)
    
    _LOGGER.info("Llama.cpp Assist conversation agent registered for entry %s", entry.entry_id)
    
    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Llama.cpp Assist integration")
    
    # Unset the conversation agent
    from homeassistant.components import conversation
    conversation.async_unset_agent(hass, entry)
    
    # Save memory before unloading
    memory_storage = hass.data[DOMAIN][entry.entry_id]["memory"]
    await memory_storage.async_save()
    
    # Clean up data
    hass.data[DOMAIN].pop(entry.entry_id)
    
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

