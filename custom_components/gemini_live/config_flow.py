"""Config flow for Gemini Live integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_CONTINUE_FOLLOWUPS,
    CONF_DETAILED_LOGGING,
    CONF_ENCOURAGE_WEB_SEARCH,
    CONF_MODEL,
    CONF_NATIVE_GOOGLE_SEARCH,
    CONF_SILENCE_DURATION_MS,
    CONF_THINKING_LEVEL,
    CONF_TRANSCRIBE_GEMINI,
    CONF_VOICE,
    DEFAULT_CONTINUE_FOLLOWUPS,
    DEFAULT_NATIVE_GOOGLE_SEARCH,
    DEFAULT_SILENCE_DURATION_MS,
    DEFAULT_THINKING_LEVEL,
    DEFAULT_TRANSCRIBE_GEMINI,
    DEFAULT_ENCOURAGE_WEB_SEARCH,
    CONF_SYSTEM_INSTRUCTION,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    AVAILABLE_VOICES_INFO,
    THINKING_LEVELS,
)
from .profiles import suggested_models


# The model field is registry-driven but accepts a custom value, so a newly
# released or renamed Live model can be entered without an integration update;
# get_profile() falls back to the default capabilities for an unknown id.
MODEL_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=model_id, label=label)
            for model_id, label in suggested_models()
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
        custom_value=True,
    )
)


SILENCE_DURATION_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=100,
        max=2000,
        step=50,
        unit_of_measurement="ms",
        mode=selector.NumberSelectorMode.SLIDER,
    )
)

THINKING_LEVEL_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=THINKING_LEVELS,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


VOICE_OPTIONS = [
    selector.SelectOptionDict(
        value=name,
        label=f"{name} - {gender}, {description}",
    )
    for name, gender, description in AVAILABLE_VOICES_INFO
]

VOICE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=VOICE_OPTIONS,
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


class GeminiLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gemini Live."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            user_input.setdefault(CONF_SYSTEM_INSTRUCTION, "")
            return self.async_create_entry(title="Gemini Live", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_MODEL, default=DEFAULT_MODEL): MODEL_SELECTOR,
                    vol.Required(CONF_VOICE, default=DEFAULT_VOICE): VOICE_SELECTOR,
                    vol.Optional(CONF_SYSTEM_INSTRUCTION): str,
                    vol.Optional(CONF_DETAILED_LOGGING, default=False): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_TRANSCRIBE_GEMINI,
                        default=DEFAULT_TRANSCRIBE_GEMINI,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENCOURAGE_WEB_SEARCH,
                        default=DEFAULT_ENCOURAGE_WEB_SEARCH,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_SILENCE_DURATION_MS,
                        default=DEFAULT_SILENCE_DURATION_MS,
                    ): SILENCE_DURATION_SELECTOR,
                    vol.Optional(
                        CONF_THINKING_LEVEL,
                        default=DEFAULT_THINKING_LEVEL,
                    ): THINKING_LEVEL_SELECTOR,
                    vol.Optional(
                        CONF_NATIVE_GOOGLE_SEARCH,
                        default=DEFAULT_NATIVE_GOOGLE_SEARCH,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_CONTINUE_FOLLOWUPS,
                        default=DEFAULT_CONTINUE_FOLLOWUPS,
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of the integration."""
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            user_input.setdefault(CONF_SYSTEM_INSTRUCTION, "")
            return self.async_update_reload_and_abort(
                entry,
                data_updates=user_input,
                options={},
            )

        config = {**entry.data, **entry.options}
        current_api_key = config.get(CONF_API_KEY, "")
        current_model = config.get(CONF_MODEL, DEFAULT_MODEL)
        current_voice = config.get(CONF_VOICE, DEFAULT_VOICE)
        current_system_instruction = config.get(CONF_SYSTEM_INSTRUCTION, "")
        current_detailed_logging = config.get(CONF_DETAILED_LOGGING, False)
        current_transcribe_gemini = config.get(
            CONF_TRANSCRIBE_GEMINI, DEFAULT_TRANSCRIBE_GEMINI
        )
        current_encourage_web_search = config.get(
            CONF_ENCOURAGE_WEB_SEARCH, DEFAULT_ENCOURAGE_WEB_SEARCH
        )
        current_silence_duration_ms = config.get(
            CONF_SILENCE_DURATION_MS, DEFAULT_SILENCE_DURATION_MS
        )
        current_thinking_level = config.get(
            CONF_THINKING_LEVEL, DEFAULT_THINKING_LEVEL
        )
        current_native_google_search = config.get(
            CONF_NATIVE_GOOGLE_SEARCH, DEFAULT_NATIVE_GOOGLE_SEARCH
        )
        current_continue_followups = config.get(
            CONF_CONTINUE_FOLLOWUPS, DEFAULT_CONTINUE_FOLLOWUPS
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY, default=current_api_key): str,
                    vol.Required(CONF_MODEL, default=current_model): MODEL_SELECTOR,
                    vol.Required(CONF_VOICE, default=current_voice): VOICE_SELECTOR,
                    vol.Optional(
                        CONF_SYSTEM_INSTRUCTION,
                        description={"suggested_value": current_system_instruction},
                    ): str,
                    vol.Optional(CONF_DETAILED_LOGGING, default=current_detailed_logging): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_TRANSCRIBE_GEMINI,
                        default=current_transcribe_gemini,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ENCOURAGE_WEB_SEARCH,
                        default=current_encourage_web_search,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_SILENCE_DURATION_MS,
                        default=current_silence_duration_ms,
                    ): SILENCE_DURATION_SELECTOR,
                    vol.Optional(
                        CONF_THINKING_LEVEL,
                        default=current_thinking_level,
                    ): THINKING_LEVEL_SELECTOR,
                    vol.Optional(
                        CONF_NATIVE_GOOGLE_SEARCH,
                        default=current_native_google_search,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_CONTINUE_FOLLOWUPS,
                        default=current_continue_followups,
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return GeminiLiveOptionsFlowHandler()


class GeminiLiveOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Gemini Live re-configuration."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            user_input.setdefault(CONF_SYSTEM_INSTRUCTION, "")
            return self.async_create_entry(title="", data=user_input)

        # Pre-populate fields with existing data or options merged
        config = {**self.config_entry.data, **self.config_entry.options}
        current_api_key = config.get(CONF_API_KEY, "")
        current_model = config.get(CONF_MODEL, DEFAULT_MODEL)
        current_voice = config.get(CONF_VOICE, DEFAULT_VOICE)
        current_system_instruction = config.get(CONF_SYSTEM_INSTRUCTION, "")
        current_detailed_logging = config.get(CONF_DETAILED_LOGGING, False)
        current_transcribe_gemini = config.get(
            CONF_TRANSCRIBE_GEMINI, DEFAULT_TRANSCRIBE_GEMINI
        )
        current_encourage_web_search = config.get(
            CONF_ENCOURAGE_WEB_SEARCH, DEFAULT_ENCOURAGE_WEB_SEARCH
        )
        current_silence_duration_ms = config.get(
            CONF_SILENCE_DURATION_MS, DEFAULT_SILENCE_DURATION_MS
        )
        current_thinking_level = config.get(
            CONF_THINKING_LEVEL, DEFAULT_THINKING_LEVEL
        )
        current_native_google_search = config.get(
            CONF_NATIVE_GOOGLE_SEARCH, DEFAULT_NATIVE_GOOGLE_SEARCH
        )
        current_continue_followups = config.get(
            CONF_CONTINUE_FOLLOWUPS, DEFAULT_CONTINUE_FOLLOWUPS
        )

        schema_dict = {
            vol.Required(CONF_API_KEY, default=current_api_key): str,
            vol.Required(CONF_MODEL, default=current_model): MODEL_SELECTOR,
            vol.Required(CONF_VOICE, default=current_voice): VOICE_SELECTOR,
            vol.Optional(
                CONF_SYSTEM_INSTRUCTION,
                description={"suggested_value": current_system_instruction},
            ): str,
            vol.Optional(CONF_DETAILED_LOGGING, default=current_detailed_logging): selector.BooleanSelector(),
            vol.Optional(
                CONF_TRANSCRIBE_GEMINI,
                default=current_transcribe_gemini,
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ENCOURAGE_WEB_SEARCH,
                default=current_encourage_web_search,
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_SILENCE_DURATION_MS,
                default=current_silence_duration_ms,
            ): SILENCE_DURATION_SELECTOR,
            vol.Optional(
                CONF_THINKING_LEVEL,
                default=current_thinking_level,
            ): THINKING_LEVEL_SELECTOR,
            vol.Optional(
                CONF_NATIVE_GOOGLE_SEARCH,
                default=current_native_google_search,
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_CONTINUE_FOLLOWUPS,
                default=current_continue_followups,
            ): selector.BooleanSelector(),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
