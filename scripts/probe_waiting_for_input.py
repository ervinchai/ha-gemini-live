"""Probe whether a Gemini Live model populates ``waiting_for_input``.

The integration uses ``response.server_content.waiting_for_input`` to decide
whether to keep the mic open for a follow-up (continue_conversation), falling
back to a trailing-question-mark heuristic when the model leaves it unset. This
script tells you, for a given model, which path you'll actually get: it opens a
Live session, nudges the model into asking a follow-up question, and reports
every ``waiting_for_input`` / ``turn_complete_reason`` value it observes.

Usage (PowerShell):
    $env:GEMINI_API_KEY = "..."
    python scripts/probe_waiting_for_input.py
    python scripts/probe_waiting_for_input.py gemini-2.5-flash-native-audio-preview-12-2025

Usage (bash):
    GEMINI_API_KEY=... python scripts/probe_waiting_for_input.py [model]

Exit code is 0 if the model populated the flag at least once, 1 if it never did
(meaning the integration relies on the question-mark fallback for that model).
"""

from __future__ import annotations

import asyncio
import os
import sys

from google import genai

DEFAULT_MODEL = "gemini-3.1-flash-live-preview"

# Two turns: the first asks the model to pose a question and wait; the second is
# a short answer, after which a well-behaved model may again wait for the user.
PROMPTS = [
    "Let's chat for a moment. Ask me one short personal question, then wait for my answer.",
    "I really enjoy hiking on weekends.",
]

# Mirror the integration: AUDIO modality with output transcription so we can see
# the reply text alongside the flag.
CONFIG = {
    "response_modalities": ["AUDIO"],
    "output_audio_transcription": {},
    "system_instruction": {
        "parts": [
            {
                "text": (
                    "You are a friendly, curious voice assistant. End each reply "
                    "with a question and then wait for the user to respond."
                )
            }
        ]
    },
}


async def probe(model: str, api_key: str) -> bool:
    """Run the probe and return whether waiting_for_input was ever set."""
    client = genai.Client(api_key=api_key)
    observed: list[bool] = []

    print(f"Connecting to {model} ...\n")
    async with client.aio.live.connect(model=model, config=CONFIG) as session:
        for prompt in PROMPTS:
            print(f">>> user: {prompt}")
            await session.send_realtime_input(text=prompt)

            transcript: list[str] = []
            async for response in session.receive():
                content = response.server_content
                if not content:
                    continue

                if content.output_transcription and content.output_transcription.text:
                    transcript.append(content.output_transcription.text)

                if content.waiting_for_input is not None:
                    observed.append(content.waiting_for_input)
                    print(f"    waiting_for_input = {content.waiting_for_input!r}")

                if content.turn_complete_reason is not None:
                    print(f"    turn_complete_reason = {content.turn_complete_reason}")

                if content.turn_complete:
                    reply = "".join(transcript).strip()
                    print(f"    <<< reply: {reply!r}\n")
                    break

    print("=" * 60)
    if observed:
        print(f"RESULT: model populated waiting_for_input {len(observed)} time(s): {observed}")
        print("-> The integration's metadata path works for this model.")
        return True
    print("RESULT: model NEVER populated waiting_for_input (always None).")
    print("-> The integration falls back to the trailing-question-mark heuristic")
    print("   for this model (needs Transcribe Gemini on for voice).")
    return False


def main() -> int:
    """Entry point."""
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in the environment.", file=sys.stderr)
        return 2
    try:
        populated = asyncio.run(probe(model, api_key))
    except Exception as exc:  # noqa: BLE001
        print(f"Probe failed: {exc}", file=sys.stderr)
        return 2
    return 0 if populated else 1


if __name__ == "__main__":
    raise SystemExit(main())
