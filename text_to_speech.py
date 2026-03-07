import os
import sys
import wave
import tempfile
from piper import PiperVoice, SynthesisConfig
from pydub import AudioSegment
from play_audio import play_audio, audio_queue

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_MODEL = os.path.join(BASE_DIR, "piper_voices", "en_US-arnold-medium.onnx")

voice = PiperVoice.load(VOICE_MODEL)

def text_to_speech(text: str):
    try:
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
