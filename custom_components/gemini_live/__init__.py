"""The Gemini Live integration."""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gemini Live from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store configuration data
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Register static path and REST API view only once
    if len(hass.data[DOMAIN]) == 1:
        _LOGGER.debug("Registering Gemini Live static path and config view")
        hass.http.register_static_path(
            "/local/gemini_live",
            hass.config.path("custom_components/gemini_live/www"),
            cache_headers=False,
        )
        hass.http.register_view(GeminiLiveConfigView(hass))

    # Forward setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["stt", "tts", "conversation"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["stt", "tts", "conversation"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class GeminiLiveConfigView(HomeAssistantView):
    """View to expose Gemini Live config safely to the authenticated browser test page."""

    url = "/api/gemini_live/config"
    name = "api:gemini_live:config"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self.hass = hass

    async def get(self, request):
        """Handle GET request."""
        entries = self.hass.data.get(DOMAIN, {})
        if not entries:
            return self.json({"error": "No config entries active"}, status_code=404)

        # Return the config from the first active entry
        first_entry_id = next(iter(entries))
        config = entries[first_entry_id]

        return self.json({
            "api_key": config.get("api_key"),
            "model": config.get("model"),
            "voice": config.get("voice"),
            "system_instruction": config.get("system_instruction"),
        })
