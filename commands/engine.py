from __future__ import annotations

import gc
import json
import time
import queue
from typing import Any

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
    throw_error,
)
from project_types import LightsLike

# silence temrinal output
# SetLogLevel(-1)

model = Model(config.VOSK_MODEL_PATH)
rec: Any = KaldiRecognizer(model, config.SAMPLE_RATE)

# Sleep mode uses its own recognizer restricted to the wake grammar. Measured on
# the Pi with an AC running, this caught 7/7 spoken wakes where the open-vocab
# recognizer caught 3/7 (it heard "they only", "they'll and", "fail", "beyond
# me"), and produced no false wakes over 25s of unrelated conversation.
wake_rec: Any = KaldiRecognizer(
    model, config.SAMPLE_RATE, json.dumps(config.WAKE_WORDS + ["[unk]"])
)
wake_rec.SetWords(True)  # per-word confidence, used to reject marginal matches

q: queue.Queue[tuple[float, bytes]] = queue.Queue(maxsize=20)


def callback(indata: Any, frames: int, time_: Any, status: Any) -> None:
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



def process_sleep_mode(
    q: queue.Queue[tuple[float, bytes]],
    wake_rec: Any,
    lights: LightsLike,
) -> bool:
    """Feed every captured block to the wake recognizer and return whether he woke.

    There is deliberately no energy gate in front of this. The USB mic is already
    at maximum hardware gain (+23.8dB, AGC off), which leaves speech only about
    2-3x above the noise floor of a running AC, so any RMS threshold high enough
    to reject the AC also rejects normal speaking volume. The grammar rejects
    non-wake audio instead, which it does without the volume sensitivity.
    """
    try:
        item = q.get(timeout=0.2)
        data = item[1] if isinstance(item, tuple) else item
    except queue.Empty:
        return False

    if not data or not wake_rec.AcceptWaveform(data):
        return False

    result = json.loads(wake_rec.Result())
    text = result.get("text", "").lower().strip()
    if config.WAKE_PHRASE not in text:
        return False

    # Score the phrase itself and ignore the [unk] filler that surrounds it, which
    # carries no useful confidence of its own.
    confidences = [
        word.get("conf", 0.0)
        for word in result.get("result", [])
        if word.get("word") != "[unk]"
    ]
    score = min(confidences) if confidences else 0.0

    if score < config.WAKE_MIN_CONFIDENCE:
        print(f"[wake] ignored {text!r} conf={score:.2f}", flush=True)
        return False

    print(f"[wake] woke on {text!r} conf={score:.2f}", flush=True)
    lights.set_color("idle")
    greet(lights, None, q)
    config.AWAKE = True
    config.CPU_MODE = True  # wake directly into CPU mode; "learning computer" path kept for revert
    wake_rec.Reset()
    return True


def _accumulate_speech(
    q: queue.Queue[tuple[float, bytes]],
    rec: Any,
    initial_text: str,
    pause_timeout: float = 1.2,
    max_wait: float = 10,
) -> str:
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


def process_awake_mode(
    lights: LightsLike,
    q: queue.Queue[tuple[float, bytes]],
    rec: Any,
) -> bool:
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


def handle_commands(lights: LightsLike) -> None:
    config.LISTENING = True
    config.AWAKE = False
    last_command_time = time.time()

    try:
        with sd.RawInputStream(
            samplerate=config.SAMPLE_RATE,
            blocksize=config.BLOCKSIZE,
            device=config.MIC_DEVICE_INDEX,
            dtype='int16',
            channels=1,
            callback=callback
        ):
            while config.LISTENING:
                if not config.AWAKE:
                    if process_sleep_mode(q, wake_rec, lights):
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
