"""Speech-to-Text platform for Gemini Live."""

import asyncio
import base64
import contextvars
import logging
from collections.abc import AsyncIterable

import aiohttp
from homeassistant.components.stt import (
    AudioMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_API_KEY, CONF_MODEL, CONF_VOICE, CONF_SYSTEM_INSTRUCTION
from .utils import pcm_to_wav, resample_24k_to_16k

_LOGGER = logging.getLogger(__name__)

# Context variable to share audio response with TTS in the same pipeline execution task
gemini_audio_response: contextvars.ContextVar[bytes] = contextvars.ContextVar("gemini_audio_response")

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gemini Live STT platform."""
    async_add_entities([GeminiLiveSTT(hass, config_entry)])


class GeminiLiveSTT(SpeechToTextEntity):
    """Gemini Live STT Entity."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the STT entity."""
        self.hass = hass
        self.entry = entry
        self._name = "Gemini Live"
        self._unique_id = f"{entry.entry_id}_stt"

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def supported_languages(self) -> list[str]:
        """Return supported languages."""
        return ["en", "en-US", "pl", "es", "fr", "de", "it"]

    @property
    def supported_formats(self) -> list[str]:
        """Return supported audio formats."""
        return ["wav", "raw"]

    @property
    def supported_rates(self) -> list[int]:
        """Return supported audio sample rates."""
        return [16000]

    @property
    def supported_channels(self) -> list[int]:
        """Return supported audio channels."""
        return [1]

    @property
    def supported_bit_widths(self) -> list[int]:
        """Return supported audio bit widths."""
        return [16]

    async def async_process_audio_stream(
        self,
        metadata: AudioMetadata,
        stream: AsyncIterable[bytes],
    ) -> SpeechResult:
        """Process the audio stream and send it directly to Gemini Live API."""
        # Reset the response audio for this session
        gemini_audio_response.set(b"")

        api_key = self.entry.data.get(CONF_API_KEY)
        model = self.entry.data.get(CONF_MODEL)
        voice = self.entry.data.get(CONF_VOICE)
        system_instruction = self.entry.data.get(CONF_SYSTEM_INSTRUCTION)

        if not api_key:
            _LOGGER.error("API Key not configured for Gemini Live")
            return SpeechResult(None, SpeechResultState.ERROR)

        # Build bidirectional WebSocket endpoint URL
        url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"

        text_response_parts = []
        audio_response_chunks = []

        session = aiohttp.ClientSession()
        try:
            _LOGGER.debug("Connecting to Gemini Live WebSocket: %s", url.split("?")[0])
            async with session.ws_connect(url) as ws:
                _LOGGER.debug("Connected to Gemini Live WebSocket")

                # Send Setup message
                setup_msg = {
                    "setup": {
                        "model": f"models/{model}",
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {
                                        "voiceName": voice
                                    }
                                }
                            }
                        },
                        "tools": [
                            {
                                "functionDeclarations": [
                                    {
                                        "name": "execute_home_assistant_intent",
                                        "description": "Execute a command to control Home Assistant devices (e.g. turn on/off lights, open/close covers, set temperature, check status, etc.).",
                                        "parameters": {
                                            "type": "OBJECT",
                                            "properties": {
                                                "command": {
                                                    "type": "STRING",
                                                    "description": "The natural language instruction to execute (e.g., 'turn off living room lights')."
                                                }
                                            },
                                            "required": ["command"]
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
                if system_instruction:
                    setup_msg["setup"]["systemInstruction"] = {
                        "parts": [{"text": system_instruction}]
                    }

                await ws.send_json(setup_msg)
                _LOGGER.debug("Sent setup message for model: %s", model)

                # Receive setupComplete acknowledgement
                msg = await ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    if "setupComplete" not in data:
                        _LOGGER.error("Expected setupComplete, got: %s", data)
                        return SpeechResult(None, SpeechResultState.ERROR)
                    _LOGGER.debug("Gemini Live session setup complete")
                else:
                    _LOGGER.error("Failed to set up Gemini Live session: %s", msg)
                    return SpeechResult(None, SpeechResultState.ERROR)

                async def send_audio():
                    """Task to read microphone audio stream and send to Gemini Live."""
                    try:
                        async for chunk in stream:
                            if not chunk:
                                continue
                            encoded = base64.b64encode(chunk).decode("utf-8")
                            input_msg = {
                                "realtimeInput": {
                                    "mediaChunks": [
                                        {
                                            "mimeType": "audio/pcm;rate=16000",
                                            "data": encoded
                                        }
                                    ]
                                }
                            }
                            await ws.send_json(input_msg)
                        _LOGGER.debug("Microphone input stream finished sending")
                    except asyncio.CancelledError:
                        _LOGGER.debug("Microphone audio sender task cancelled")
                    except Exception as e:
                        _LOGGER.error("Error in send_audio: %s", e)

                async def receive_responses():
                    """Task to read responses from Gemini Live."""
                    try:
                        async for response_msg in ws:
                            if response_msg.type == aiohttp.WSMsgType.TEXT:
                                data = response_msg.json()
                                
                                # Handle Tool Calls (Smart Home Control)
                                if "toolCall" in data:
                                    from homeassistant.core import Context
                                    from homeassistant.components import conversation
                                    
                                    function_calls = data["toolCall"].get("functionCalls", [])
                                    for call in function_calls:
                                        if call.get("name") == "execute_home_assistant_intent":
                                            call_id = call.get("id")
                                            args = call.get("args", {})
                                            command_str = args.get("command")
                                            
                                            _LOGGER.info("Gemini Live requested tool execution: %s", command_str)
                                            
                                            try:
                                                result = await conversation.async_converse(
                                                    hass=self.hass,
                                                    text=command_str,
                                                    conversation_id=None,
                                                    context=Context(),
                                                    agent_id="conversation.home_assistant",
                                                )
                                                
                                                speech_text = "Command executed successfully"
                                                if result.response and result.response.speech and "plain" in result.response.speech:
                                                    speech_text = result.response.speech["plain"].get("speech", speech_text)
                                            except Exception as err:
                                                _LOGGER.error("Failed to execute Home Assistant intent: %s", err)
                                                speech_text = f"Error executing command: {str(err)}"
                                                
                                            # Send result back to Gemini Live session
                                            response_msg = {
                                                "toolResponse": {
                                                    "functionResponses": [
                                                        {
                                                            "response": {
                                                                "output": speech_text
                                                            },
                                                            "id": call_id
                                                        }
                                                    ]
                                                }
                                            }
                                            await ws.send_json(response_msg)
                                            _LOGGER.debug("Sent tool response back to Gemini Live")

                                if "serverContent" in data:
                                    content = data["serverContent"]
                                    if "modelTurn" in content:
                                        parts = content["modelTurn"].get("parts", [])
                                        for part in parts:
                                            if "text" in part:
                                                text_response_parts.append(part["text"])
                                            if "inlineData" in part:
                                                audio_data = part["inlineData"].get("data")
                                                if audio_data:
                                                    audio_bytes = base64.b64decode(audio_data)
                                                    audio_response_chunks.append(audio_bytes)

                                    if content.get("turnComplete"):
                                        _LOGGER.debug("Gemini Live response turn complete")
                                        break
                            elif response_msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                _LOGGER.debug("WebSocket closed or error in receive_responses")
                                break
                    except Exception as e:
                        _LOGGER.error("Error in receive_responses: %s", e)

                # Run sender and receiver tasks concurrently
                send_task = asyncio.create_task(send_audio())
                receive_task = asyncio.create_task(receive_responses())

                # Wait for either sender or receiver to finish
                done, pending = await asyncio.wait(
                    [send_task, receive_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                if receive_task in done:
                    # Connection closed or model completed turn first (e.g. barge-in or error)
                    if not send_task.done():
                        send_task.cancel()
                else:
                    # Sender finished (user stopped speaking). Wait for model response to complete
                    try:
                        await asyncio.wait_for(receive_task, timeout=10.0)
                    except asyncio.TimeoutError:
                        _LOGGER.warning("Timeout waiting for Gemini Live response")
                        if not receive_task.done():
                            receive_task.cancel()

                # Process results
                response_text = "".join(text_response_parts)
                all_audio_24k = b"".join(audio_response_chunks)

                if all_audio_24k:
                    # Resample from 24kHz down to 16kHz PCM
                    resampled_pcm = resample_24k_to_16k(all_audio_24k)
                    # Convert to standard WAV format
                    wav_data = pcm_to_wav(resampled_pcm, 16000)
                    # Save in ContextVar for TTS retrieval
                    gemini_audio_response.set(wav_data)
                    _LOGGER.debug(
                        "Received response: text length %d chars, audio length %d bytes (resampled %d bytes)",
                        len(response_text), len(all_audio_24k), len(wav_data)
                    )
                else:
                    _LOGGER.warning("No audio response received from Gemini Live")

                return SpeechResult(response_text, SpeechResultState.SUCCESS)

        except Exception as e:
            _LOGGER.exception("Error in Gemini Live STT process: %s", e)
            return SpeechResult(None, SpeechResultState.ERROR)
        finally:
            await session.close()
