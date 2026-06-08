"""Utility functions for audio processing."""

import struct

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw 16-bit signed PCM mono audio in a WAV container."""
    num_channels = 1
    sample_width = 2  # 16-bit

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm_data),
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM format code
        num_channels,
        sample_rate,
        sample_rate * num_channels * sample_width,
        num_channels * sample_width,
        sample_width * 8,
        b"data",
        len(pcm_data),
    )
    return header + pcm_data

def resample_24k_to_16k(data: bytes) -> bytes:
    """Resample raw 16-bit signed PCM mono audio from 24kHz down to 16kHz using linear interpolation."""
    num_samples = len(data) // 2
    if num_samples == 0:
        return b""

    samples = struct.unpack(f"<{num_samples}h", data)
    output = []
    i = 0
    while i < num_samples - 2:
        output.append(samples[i])
        output.append((samples[i+1] + samples[i+2]) // 2)
        i += 3
    if i < num_samples:
        output.append(samples[i])

    return struct.pack(f"<{len(output)}h", *output)
