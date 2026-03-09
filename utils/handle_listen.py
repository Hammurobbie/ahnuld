import sounddevice as sd
import numpy as np


def is_speech(block, threshold):
    """
    Simple RMS-based VAD (voice activity detection).
    block: np.ndarray audio block
    threshold: float, energy level to treat as speech
    """
    rms = np.sqrt(np.mean(block ** 2))
    return rms > threshold


def listen_for_speech(samplerate=48000, blocksize=1024, threshold=0.03):
    """
    Generator that yields audio blocks only when speech is detected.
    Keeps CPU low during silence.
    """
    with sd.InputStream(samplerate=samplerate, channels=1, dtype='int16') as stream:
        while True:
            block, _ = stream.read(blocksize)
            block = block.astype(np.float32) / 32768.0

            if is_speech(block, threshold):
                yield block
