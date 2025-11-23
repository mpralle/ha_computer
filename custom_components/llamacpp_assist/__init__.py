"""The Llama.cpp Assist integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .memory import MemoryStorage

if TYPE_CHECKING:
    from .conversation import LlamaCppConversationEntity

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CONVERSATION]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Llama.cpp Assist from a config entry."""
    _LOGGER.debug("Setting up Llama.cpp Assist integration")
    
    # Initialize memory storage
    memory_storage = MemoryStorage(hass)
    await memory_storage.async_load()
    
    # Store in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "memory": memory_storage,
    }
    
    # Forward to conversation platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    _LOGGER.info("Llama.cpp Assist integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Llama.cpp Assist integration")
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Save memory before unloading
        memory_storage = hass.data[DOMAIN][entry.entry_id]["memory"]
        await memory_storage.async_save()
        
        # Clean up data
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
