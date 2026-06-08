"""Config flow for Gemini Live integration."""

import voluptuous as vol
from homeassistant import config_entries
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_MODEL,
    CONF_VOICE,
    CONF_SYSTEM_INSTRUCTION,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    AVAILABLE_MODELS,
    AVAILABLE_VOICES,
)

class GeminiLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gemini Live."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="Gemini Live", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_MODEL, default=DEFAULT_MODEL): vol.In(AVAILABLE_MODELS),
                    vol.Required(CONF_VOICE, default=DEFAULT_VOICE): vol.In(AVAILABLE_VOICES),
                    vol.Optional(CONF_SYSTEM_INSTRUCTION): str,
                }
            ),
            errors=errors,
        )
