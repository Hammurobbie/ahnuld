from __future__ import annotations

import os
import io
import threading
import time
import soundfile as sf
import sounddevice as sd
from queue import Queue
from datetime import datetime
from pydub import AudioSegment

import commands.config as config

MIC_DEVICE_INDEX: int = config.MIC_DEVICE_INDEX
OUTPUT_DEVICE_INDEX: int = config.OUTPUT_DEVICE_INDEX
sd.default.device = (MIC_DEVICE_INDEX, OUTPUT_DEVICE_INDEX)

audio_queue: Queue[tuple[str, bool] | None] = Queue()
# Held through playback plus a short tail, so the mic misses his own voice.
_speaking = threading.Event()


def is_speaking() -> bool:
    return _speaking.is_set()


def audio_worker() -> None:
    while True:
        item = audio_queue.get()
        if item is None:
            break
        _speaking.set()
        try:
            file_path, is_full_path = item

            if is_full_path:
                actual_path = file_path
            else:
                _audio_dir = os.path.join(os.path.dirname(__file__), "ahnuld_audio")
                actual_path = os.path.join(_audio_dir, f"{file_path}.wav")

            audio = AudioSegment.from_file(actual_path, format="wav")

            # Reduce volume during quiet hours (12am - 7am)
            current_hour = datetime.now().hour
            if 0 <= current_hour < 6:
                audio = audio - 15  # Reduce by 15 dB

            audio = audio.set_frame_rate(48000).set_channels(2)
            buf = io.BytesIO()
            audio.export(buf, format="wav")
            buf.seek(0)
            data, fs = sf.read(buf)
            sd.play(data, fs, device=OUTPUT_DEVICE_INDEX)
            sd.wait()
            time.sleep(0.4)

            if is_full_path and os.path.exists(actual_path):
                try:
                    os.unlink(actual_path)
                except:
                    pass

        except Exception as e:
            # print(f"Audio playback error: {e}")
            pass
        finally:
            audio_queue.task_done()
            if audio_queue.empty():
                _speaking.clear()

threading.Thread(target=audio_worker, daemon=True, name="AudioWorker").start()

def play_audio(file_name: str, is_file: bool = False) -> None:
    audio_queue.put((file_name, is_file))


def shutdown_audio() -> None:
    audio_queue.put(None)
    audio_queue.join()
