"""Per-model profile/adapter abstraction for Gemini Live.

A :class:`ModelProfile` encapsulates everything that differs between Gemini
Live models: which ``LiveConnectConfig`` keys are safe to emit, the response
quirks the receive loop has to tolerate, and the audio/voice/language surface
the rest of the integration advertises.

Emitting a config key a model does not understand breaks *every* connection to
that model, so request building is centralised here and gated on capability
flags. Selecting a model selects its adapter; the STT path, the text path and
the session manager all consume the adapter rather than branching on model id
strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from google.genai import types

from .const import (
    AVAILABLE_VOICES,
    DEFAULT_MODEL,
    SUPPORTED_LANGUAGES,
)


@dataclass(frozen=True)
class ModelCapabilities:
    """What a Live model supports, keyed only by the profile that owns it.

    Every flag defaults to the conservative choice so that an unknown model id
    falls back to a minimal, broadly-compatible session rather than emitting a
    config key that might break the connection.
    """

    # Request-building capabilities. A False flag means "never emit this key".
    supports_thinking_config: bool = False
    supports_session_resumption: bool = False
    supports_context_compression: bool = False
    supports_vad_silence_config: bool = False
    can_combine_google_search_with_functions: bool = False
    supports_nonblocking_tools: bool = False

    # Audio surface.
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000
    response_modalities: tuple[str, ...] = ("AUDIO",)

    # Voices and languages the model can speak. Default to the full catalogue.
    supported_voices: tuple[str, ...] = tuple(AVAILABLE_VOICES)
    supported_languages: tuple[str, ...] = tuple(SUPPORTED_LANGUAGES)

    # Response quirk: some native-audio models emit ``turn_complete`` *before*
    # the audio for the turn arrives. The receive loop must not end the turn on
    # that first ``turn_complete`` for those models.
    emits_turn_complete_before_audio: bool = False


@dataclass(frozen=True)
class LiveSettings:
    """User/runtime settings handed to a profile to build a Live config.

    The profile decides which of these actually reach the wire based on its
    capabilities; callers always pass the full set. Capability-gated knobs
    default to "off" so a profile that does not support them stays silent.
    """

    voice: str
    system_instruction: str
    gemini_tools: list[dict[str, Any]] = field(default_factory=list)
    transcribe_output: bool = False

    # Capability-gated latency / continuity knobs. ``None`` / ``False`` mean
    # "leave the model default in place" and nothing is emitted.
    silence_duration_ms: int | None = None
    thinking_level: str | None = None
    native_google_search: bool = False
    session_resumption: bool = False
    context_compression: bool = False


class ModelProfile:
    """Adapter that builds requests for, and reads responses from, one model.

    Subclasses (or instances with different capabilities) describe a concrete
    model; the registry maps a model id to the right instance.
    """

    def __init__(
        self,
        model_id: str,
        capabilities: ModelCapabilities,
        *,
        label: str | None = None,
    ) -> None:
        """Initialise a profile for ``model_id``."""
        self.model_id = model_id
        self.capabilities = capabilities
        self.label = label or model_id

    # -- request building --------------------------------------------------

    def build_live_config(self, settings: LiveSettings) -> dict[str, Any]:
        """Assemble the ``LiveConnectConfig`` dict for this model.

        Only keys the model supports are emitted; the result is validated
        against the SDK's pydantic model so an unsupported key is caught here
        rather than silently breaking the websocket on connect.
        """
        caps = self.capabilities
        config: dict[str, Any] = {
            "response_modalities": list(caps.response_modalities),
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": settings.voice}
                }
            },
            "system_instruction": {
                "parts": [{"text": settings.system_instruction}]
            },
            "input_audio_transcription": {},
            "realtime_input_config": {
                "turn_coverage": "TURN_INCLUDES_ONLY_ACTIVITY"
            },
        }
        if settings.transcribe_output:
            config["output_audio_transcription"] = {}

        self._apply_vad(config, settings)
        self._apply_continuity(config, settings)
        self._apply_thinking(config, settings)
        self._apply_tools(config, settings)

        self._validate(config)
        return config

    def _apply_vad(self, config: dict[str, Any], settings: LiveSettings) -> None:
        """Emit the end-of-speech silence knob when supported and requested."""
        if (
            self.capabilities.supports_vad_silence_config
            and settings.silence_duration_ms is not None
        ):
            config["realtime_input_config"]["automatic_activity_detection"] = {
                "silence_duration_ms": settings.silence_duration_ms,
            }

    def _apply_continuity(
        self, config: dict[str, Any], settings: LiveSettings
    ) -> None:
        """Emit session resumption / context compression when supported."""
        if self.capabilities.supports_session_resumption and settings.session_resumption:
            config["session_resumption"] = {}
        if self.capabilities.supports_context_compression and settings.context_compression:
            config["context_window_compression"] = {"sliding_window": {}}

    def _apply_thinking(
        self, config: dict[str, Any], settings: LiveSettings
    ) -> None:
        """Emit the thinking level when supported and requested."""
        if (
            self.capabilities.supports_thinking_config
            and settings.thinking_level is not None
        ):
            config["thinking_config"] = {"thinking_level": settings.thinking_level}

    def _apply_tools(
        self, config: dict[str, Any], settings: LiveSettings
    ) -> None:
        """Emit the tool list, combining native search with functions if able.

        Models that cannot combine the built-in Google Search tool with custom
        function declarations only ever receive the function declarations.
        """
        tools: list[dict[str, Any]] = []
        if (
            settings.native_google_search
            and self.capabilities.can_combine_google_search_with_functions
        ):
            tools.append({"google_search": {}})
        tools.extend(settings.gemini_tools)
        if tools:
            config["tools"] = tools

    @staticmethod
    def _validate(config: dict[str, Any]) -> None:
        """Validate a built config against the SDK's pydantic model."""
        types.LiveConnectConfig.model_validate(config)

    # -- response handling -------------------------------------------------

    def turn_complete_is_final(self, *, received_audio: bool) -> bool:
        """Whether a ``turn_complete`` event actually ends the turn.

        Native-audio models can report ``turn_complete`` before producing any
        audio; for them the turn only ends once audio has been seen.
        """
        if self.capabilities.emits_turn_complete_before_audio:
            return received_audio
        return True

    def with_model_id(self, model_id: str) -> "ModelProfile":
        """Return a copy of this profile bound to ``model_id``.

        Used to give an unrecognised-but-compatible model id the default
        capability set without inventing a registry entry for it.
        """
        return ModelProfile(model_id, self.capabilities, label=model_id)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Gemini 3.1 Live: the default target. Supports the full 3.x feature set —
# thinking levels, session resumption, context compression, configurable VAD
# silence, and combining native Google Search with function tools in one
# session. It does not (yet) expose NON_BLOCKING tool calls.
_GEMINI_3_1 = ModelProfile(
    "gemini-3.1-flash-live-preview",
    ModelCapabilities(
        supports_thinking_config=True,
        supports_session_resumption=True,
        supports_context_compression=True,
        supports_vad_silence_config=True,
        can_combine_google_search_with_functions=True,
        supports_nonblocking_tools=False,
        input_sample_rate=16000,
        output_sample_rate=24000,
    ),
    label="Gemini 3.1 Flash Live (preview)",
)

# Gemini 2.5 native-audio: kept so adding a non-3.x model stays trivial. Its
# defining quirk is that ``turn_complete`` can precede audio. We deliberately do
# not invest in its 2.5-only runtime features (NON_BLOCKING tools, affective
# dialog, proactivity); the flags below describe only what the integration uses.
_GEMINI_2_5_NATIVE_AUDIO = ModelProfile(
    "gemini-2.5-flash-native-audio-preview-12-2025",
    ModelCapabilities(
        supports_thinking_config=False,
        supports_session_resumption=True,
        supports_context_compression=True,
        supports_vad_silence_config=True,
        can_combine_google_search_with_functions=False,
        supports_nonblocking_tools=True,
        input_sample_rate=16000,
        output_sample_rate=24000,
        emits_turn_complete_before_audio=True,
    ),
    label="Gemini 2.5 Flash native audio (preview)",
)

_REGISTRY: dict[str, ModelProfile] = {
    _GEMINI_3_1.model_id: _GEMINI_3_1,
    _GEMINI_2_5_NATIVE_AUDIO.model_id: _GEMINI_2_5_NATIVE_AUDIO,
}

DEFAULT_PROFILE = _REGISTRY[DEFAULT_MODEL]


def get_profile(model_id: str | None) -> ModelProfile:
    """Return the profile for ``model_id``.

    A registered id returns its profile. An unknown (e.g. newly released or
    user-typed) id returns the default profile bound to that id, so a freshly
    named Live model works without an integration update.
    """
    if not model_id:
        return DEFAULT_PROFILE
    profile = _REGISTRY.get(model_id)
    if profile is not None:
        return profile
    return DEFAULT_PROFILE.with_model_id(model_id)


def suggested_models() -> list[tuple[str, str]]:
    """Return ``(model_id, label)`` pairs for the config-flow selector."""
    return [(profile.model_id, profile.label) for profile in _REGISTRY.values()]
