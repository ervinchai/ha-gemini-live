"""Text-to-Speech platform for Gemini Live."""

import logging
from typing import Any
from homeassistant.components.tts import (
    TextToSpeechEntity,
    TtsAudioType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .stt import gemini_audio_response
from .utils import pcm_to_wav

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gemini Live TTS platform."""
    async_add_entities([GeminiLiveTTS(hass, config_entry)])


class GeminiLiveTTS(TextToSpeechEntity):
    """Gemini Live TTS Entity."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the TTS entity."""
        self.hass = hass
        self.entry = entry
        self._name = "Gemini Live"
        self._unique_id = f"{entry.entry_id}_tts"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["en", "en-US", "pl", "es", "fr", "de", "it"]

    @property
    def supported_options(self) -> list[str]:
        """Return supported options."""
        return []

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any] | None = None,
    ) -> TtsAudioType:
        """Retrieve the cached audio response from the ContextVar."""
        wav_data = gemini_audio_response.get(None)
        if wav_data:
            _LOGGER.debug("TTS: Playing cached Gemini Live response (length %d bytes)", len(wav_data))
            return "wav", wav_data

        _LOGGER.warning("TTS: No cached audio found for session, returning dummy silence")
        return "wav", self._get_dummy_wav()

    def _get_dummy_wav(self) -> bytes:
        """Return 1 second of silence as 16kHz mono 16-bit PCM WAV."""
        # 16000 samples/sec * 2 bytes/sample * 1 sec = 32000 bytes of zero
        pcm_data = b"\x00" * 32000
        return pcm_to_wav(pcm_data, 16000)
