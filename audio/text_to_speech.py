import os
import re
import sys
import wave
import tempfile
from piper import PiperVoice, SynthesisConfig
from pydub import AudioSegment
from audio.play_audio import play_audio, audio_queue

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_MODEL = os.path.join(_BASE_DIR, "piper_voices", "en_US-arnold-medium.onnx")

voice = PiperVoice.load(VOICE_MODEL)

# Characters Piper pronounces literally ("asterisk", "underscore", "hash"...) that
# are almost always LLM-markdown noise, never meaningful when spoken aloud.
_TTS_NOISE_CHARS = re.compile(r"[*_`~|<>^\\#]")


def _sanitize_for_tts(text: str) -> str:
    # Keep the visible text of markdown links: [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Drop fenced code block markers but keep the code's words.
    text = re.sub(r"```[A-Za-z0-9_+-]*", "", text)
    # Drop the noise punctuation outright.
    text = _TTS_NOISE_CHARS.sub("", text)
    # Collapse runs of whitespace introduced by the strips above.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def text_to_speech(text: str) -> None:
    try:
        text = _sanitize_for_tts(text)
        if not text:
            return

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        syn_config = SynthesisConfig(
            volume=1.5,  # half as loud
            # length_scale=2.0,  # twice as slow
            # noise_scale=1.0,  # more audio variation
            # noise_w_scale=1.0,  # more speaking variation
            # normalize_audio=False, # use raw audio from voice
        )

        with wave.open(tmp_path, 'wb') as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)

        seg = AudioSegment.from_file(tmp_path, format="wav")
        seg.export(tmp_path, format="wav")

        play_audio(tmp_path, is_file=True)
        audio_queue.join()

    except Exception as e:
        # print(f"TTS Error: {e}")
        pass

if __name__ == "__main__":
    text_to_speech(sys.argv[1])
