# Changelog

All notable changes to Gemini Live for Home Assistant are documented here.

This integration is separately maintained by [@ervinchai](https://github.com/ervinchai)
and builds on the original [matt123p/ha-gemini-live](https://github.com/matt123p/ha-gemini-live).

## 2.0.0

Re-architected around a model-agnostic adapter and added latency, streaming, and
conversation controls.

- **Multi-model architecture.** Request building and response handling now live
  behind a per-model profile/adapter keyed by model id, instead of model-string
  checks. Selecting a model selects its adapter; the STT, conversation, and
  session-manager paths all consume it. `gemini-3.1-flash-live-preview` is the
  default profile, and adding a new model is a single registry entry.
- **Free-text, registry-driven model field.** The model selector is derived from
  the profile registry and accepts a custom value, so a newly released Live model
  works without an integration update.
- **Session resumption and context compression.** Long conversations resume after
  an idle disconnect or `GoAway` instead of starting cold, and the context window
  is compressed to avoid mid-session termination (where the profile supports it).
- **Latency knobs.** Configurable end-of-speech VAD silence (the main
  "respond instantly" control) and Gemini thinking level (time-to-first-audio).
- **Native Google Search.** Gemini 3.x can combine its built-in Google Search
  with Home Assistant tools in one session — no separate search agent hop. (The
  previous official-integration search workaround is no longer required on 3.x.)
- **Continuous conversation.** The microphone stays open between turns so you can
  keep talking without the wake word; the conversation ends when you ask the
  assistant to stop or fall silent (resolves
  [matt123p/ha-gemini-live#1](https://github.com/matt123p/ha-gemini-live/issues/1)).
- **Performance.** One shared Gemini client per config entry, quieter hot-path
  logging, and bounded synchronous tool calls so a slow tool cannot stall a turn.

## 1.0.1

- Fixed HACS and Hassfest validation metadata.

## 1.0.0

- Added Gemini Live speech-to-text, conversation, and cached native-audio
  text-to-speech entities.
- Added HACS metadata, brand assets, translations, validation workflow, and
  installation documentation.
