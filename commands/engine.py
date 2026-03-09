import gc
import sys
import json
import time
import queue
from thefuzz import fuzz
import sounddevice as sd
from audio import play_audio
from commands.cpu_mode import handle_cpu_mode
from vosk import Model, KaldiRecognizer, SetLogLevel

import commands.config as config
from commands.actions import (
    greet,
    sleep,
    execute_command,
    throw_error
)
from utils import listen_for_speech

SetLogLevel(-1)

model = Model(config.VOSK_MODEL_PATH)
rec = KaldiRecognizer(model, config.SAMPLE_RATE)
q = queue.Queue(maxsize=20)

def callback(indata, frames, time_, status):
    try:
        if status:
            pass
        now = time.time()

        try:
            while not q.empty():
                timestamp, _ = q.queue[0]
                if now - timestamp > 30:
                    q.get_nowait()
                else:
                    break
        except Exception:
            pass

        item = (now, bytes(indata))

        if q.full():
            q.get_nowait()
        q.put_nowait(item)

    except Exception:
        pass



def process_sleep_mode(q, rec, lights, speech_heard, speech_timer):
    woke_up = False
    times_up = (time.time() - speech_timer) > 5

    if not speech_heard:
        for block in listen_for_speech():
            speech_heard = True
            speech_timer = time.time()
            break

    if speech_heard:
        try:
            item = q.get(timeout=0.2)
            data = item[1] if isinstance(item, tuple) else item
        except queue.Empty:
            return speech_heard, speech_timer, woke_up

        if data and rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            full_text = result.get("text", "").lower().strip()

            if full_text and (
                "hey arnold" in full_text or
                fuzz.ratio("hey arnold", full_text) >= 90
            ):
                lights.set_color("idle")
                greet(lights, None, q)
                config.AWAKE = True
                config.CPU_MODE = True  # wake directly into CPU mode; "learning computer" path kept for revert
                speech_heard = False
                speech_timer = time.time()
                woke_up = True

    if speech_heard and times_up:
        speech_heard = False

    return speech_heard, speech_timer, woke_up


def _accumulate_speech(q, rec, initial_text, pause_timeout=0.8, max_wait=10):
    """After Vosk finalizes a phrase, keep listening briefly to catch
    continuation speech that was split by a brief pause."""
    accumulated = initial_text
    deadline = time.time() + pause_timeout
    hard_deadline = time.time() + max_wait

    while time.time() < min(deadline, hard_deadline):
        try:
            item = q.get(timeout=0.1)
            data = item[1] if isinstance(item, tuple) else item
        except queue.Empty:
            continue

        if not data:
            continue

        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            chunk = result.get("text", "").lower().strip()
            if chunk:
                accumulated += " " + chunk
                deadline = time.time() + pause_timeout
        else:
            partial = json.loads(rec.PartialResult())
            if partial.get("partial", "").strip():
                deadline = time.time() + pause_timeout

    return accumulated.strip()


def process_awake_mode(lights, q, rec):
    try:
        item = q.get(timeout=0.2)
        data = item[1] if isinstance(item, tuple) else item
    except queue.Empty:
        return False

    full_text=""
    if data and rec.AcceptWaveform(data):
        result = json.loads(rec.Result())
        full_text = result.get("text", "").lower().strip()

    if full_text and not config.BUSY:
        if "learning computer" in full_text:
            config.CPU_MODE = True
            play_audio("absolutely_yeah")
            lights.set_color("idle")
            time.sleep(2)
            with q.mutex:
                q.queue.clear()
            return True

        if config.CPU_MODE:
            full_text = _accumulate_speech(q, rec, full_text)

        is_query = len(full_text) > 7 and len(full_text.split()) > 1

        if config.CPU_MODE and not config.BUSY and is_query:
            handle_cpu_mode(full_text, q, lights)
            return True

        best_match = None
        highest_score = 0
        threshold = 85

        for command in config.COMMANDS:
            score = fuzz.partial_ratio(command["cmd"], full_text)
            if score > highest_score and score >= threshold:
                best_match = command
                highest_score = score

        if best_match:
            execute_command(best_match, lights, full_text)
            return True

    return False


def handle_commands(lights):
    config.LISTENING = True
    config.AWAKE = False
    last_command_time = time.time()
    speech_heard = False
    speech_timer = time.time()

    try:
        mic_info = sd.query_devices(config.MIC_DEVICE_INDEX)
        _ = mic_info['max_input_channels']

        with sd.RawInputStream(
            samplerate=config.SAMPLE_RATE,
            blocksize=8000,
            dtype='int16',
            channels=1,
            callback=callback
        ):
            while config.LISTENING:
                if not config.AWAKE:
                    speech_heard, speech_timer, woke_up = process_sleep_mode(
                        q, rec, lights, speech_heard, speech_timer
                    )
                    if woke_up:
                        last_command_time = time.time()
                else:
                    command_processed = process_awake_mode(lights, q, rec)
                    if command_processed:
                        last_command_time = time.time()

                    awake_time = 25 if config.CPU_MODE else 15
                    if config.AWAKE and (time.time() - last_command_time > awake_time):
                        sleep(lights)

    except Exception as e:
        throw_error(lights, e)
    finally:
        gc.collect()
