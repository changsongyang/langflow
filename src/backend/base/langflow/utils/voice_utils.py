import asyncio
import base64

import numpy as np
import pyaudio
import simpleaudio
from scipy.signal import resample_poly, resample

from langflow.logging import logger

SAMPLE_RATE_24K = 24000
VAD_SAMPLE_RATE_16K = 16000
FRAME_DURATION_MS = 20
BYTES_PER_SAMPLE = 2

BYTES_PER_24K_FRAME = int(SAMPLE_RATE_24K * FRAME_DURATION_MS / 1000) * BYTES_PER_SAMPLE
BYTES_PER_16K_FRAME = int(VAD_SAMPLE_RATE_16K * FRAME_DURATION_MS / 1000) * BYTES_PER_SAMPLE

def resample_24k_to_16k(frame_24k_bytes: bytes) -> bytes:
    import numpy as np
    from scipy.signal import resample_poly

    # Convert bytes to NumPy array
    samples_24k = np.frombuffer(frame_24k_bytes, dtype=np.int16)
    # Resample from 24kHz -> 16kHz
    samples_16k = resample(samples_24k, 320)
    # Convert back to int16
    samples_16k = np.rint(samples_16k).astype(np.int16)
    frame_16k_bytes = samples_16k.tobytes()

    return frame_16k_bytes

#def resample_24k_to_16k(frame_24k_bytes: bytes) -> bytes:
#    """
#    Convert one 20ms chunk (960 bytes @ 24kHz) to 20ms @ 16kHz (640 bytes).
#    Raises ValueError if the frame is not exactly 960 bytes.
#    """
#    if len(frame_24k_bytes) != BYTES_PER_24K_FRAME:
#        raise ValueError(
#            f"Expected exactly {BYTES_PER_24K_FRAME} bytes for a 20ms 24k frame, "
#            f"but got {len(frame_24k_bytes)}"
#        )
#    # Convert bytes -> int16 array (480 samples)
#    samples_24k = np.frombuffer(frame_24k_bytes, dtype=np.int16)
#
#    # Resample 24k => 16k (ratio=2/3)
#    # Should get 320 samples out if the chunk was exactly 480 samples in
#    samples_16k = resample_poly(samples_24k, up=2, down=3)
#
#    # Round & convert to int16
#    samples_16k = np.rint(samples_16k).astype(np.int16)
#
#    # Convert back to bytes
#    frame_16k_bytes = samples_16k.tobytes()
#    if len(frame_16k_bytes) != BYTES_PER_16K_FRAME:
#        raise ValueError(
#            f"Expected exactly {BYTES_PER_16K_FRAME} bytes after resampling "
#            f"to 20ms@16kHz, got {len(frame_16k_bytes)}"
#        )
#    return frame_16k_bytes
#

async def write_audio_to_file(audio_base64: str, filename: str = "output_audio.raw") -> None:
    """
    Decode the base64-encoded audio and write (append) it to a file asynchronously.
    """
    try:
        audio_bytes = base64.b64decode(audio_base64)
        # Use asyncio.to_thread to perform file I/O without blocking the event loop
        await asyncio.to_thread(lambda: open(filename, "ab").write(audio_bytes))
        logger.info(f"Wrote {len(audio_bytes)} bytes to {filename}")
    except Exception as e:
        logger.error(f"Error writing audio to file: {e}")
