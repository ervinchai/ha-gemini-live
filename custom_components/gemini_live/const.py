"""Constants for the Gemini Live integration."""

DOMAIN = "gemini_live"

CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_VOICE = "voice"
CONF_SYSTEM_INSTRUCTION = "system_instruction"

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_VOICE = "Puck"

AVAILABLE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-live-preview",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-live-preview",
]

AVAILABLE_VOICES = ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]
