from __future__ import annotations

import gc
import glob
import json
import subprocess
import time
import queue
import re
from collections import deque
from typing import Any

from thefuzz import fuzz
import sounddevice as sd
from audio import play_audio, is_speaking
from commands.cpu_mode import handle_cpu_mode
from vosk import Model, KaldiRecognizer, SetLogLevel

import commands.config as config
from commands.actions import (
    greet,
    sleep,
    execute_command,
    throw_error,
    turn_on_lights,
    turn_off_lights,
)
from project_types import LightsLike

# silence temrinal output
# SetLogLevel(-1)

model = Model(config.VOSK_MODEL_PATH)
rec: Any = KaldiRecognizer(model, config.SAMPLE_RATE)

# Sleep mode uses its own recognizer, restricted to the wake phrase plus decoys.
# The full model is far worse at this: on the same audio it caught 3/7 spoken
# wakes to the grammar's 7/7, hearing "they only", "they'll and", "fail" and
# "beyond me" instead.
wake_rec: Any = KaldiRecognizer(
    model,
    config.SAMPLE_RATE,
    json.dumps(config.WAKE_WORDS + config.WAKE_DECOYS + ["[unk]"]),
)
wake_rec.SetWords(True)  # per-word confidence, used to reject marginal matches

wake_model = None
if config.WAKE_BACKEND == "model":
    from commands.wakeword import HeyArnoldWake

    wake_model = HeyArnoldWake(config.WAKE_MODEL_DIR)

# Lights requests are re-decoded against theme names only. Open vocabulary turns
# "sunset" and "boston" into whatever common words sound close.
theme_rec: Any = KaldiRecognizer(
    model,
    config.SAMPLE_RATE,
    json.dumps(list(config.THEME_PHRASES) + config.THEME_GRAMMAR_FILLER + ["[unk]"]),
)
theme_rec.SetWords(True)

sleep_rec: Any = KaldiRecognizer(
    model,
    config.SAMPLE_RATE,
    json.dumps(
        config.SLEEP_GRAMMAR_PHRASES
        + config.WAKE_DECOYS
        + config.THEME_GRAMMAR_FILLER
        + ["[unk]"]
    ),
)

q: queue.Queue[tuple[float, bytes]] = queue.Queue(maxsize=20)

# Copy of the most recent mic audio, independent of q (which the recognizers drain).
_recent_audio: deque[tuple[float, bytes]] = deque(
    maxlen=int(config.THEME_AUDIO_SECONDS * config.SAMPLE_RATE / config.BLOCKSIZE) + 2
)
_awake_since = 0.0
# Ignore the mic briefly after sleep so the wake that just fired cannot fire again.
_deaf_until = 0.0

_SLEEP_WORDS = frozenset({"sleep", "asleep"})
_SLEEP_LEADS = frozenset({"go", "going", "gonna", "gotta", "got"})


def callback(indata: Any, frames: int, time_: Any, status: Any) -> None:
    try:
        if is_speaking():
            return
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
        _recent_audio.append(item)

        if q.full():
            q.get_nowait()
        q.put_nowait(item)

    except Exception:
        pass



def _phrase_confidence(words: list[dict[str, Any]], phrase: str) -> float | None:
    """Lowest confidence among the words forming the wake phrase, or None if absent.

    Scores the phrase alone. Decoys and [unk] routinely sit either side of it and
    their confidence says nothing about whether the phrase itself was spoken, so
    including them would let an unrelated neighbouring word veto a real wake.
    """
    target = phrase.split()
    spoken = [word.get("word", "").lower() for word in words]

    for i in range(len(spoken) - len(target) + 1):
        if spoken[i:i + len(target)] == target:
            return min(word.get("conf", 0.0) for word in words[i:i + len(target)])

    return None


def _is_sleep_request(text: str) -> bool:
    words = text.split()
    for index, word in enumerate(words):
        if word not in _SLEEP_WORDS:
            continue
        lead = set(words[max(0, index - 3):index])
        if lead & _SLEEP_LEADS:
            return True
    return False


_awake_khz: int | None = None
_cpu_clock_broken = False


def _cpu_max_path() -> str | None:
    paths = sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_max_freq"))
    return paths[0] if paths else None


def _read_khz(path: str) -> int | None:
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except OSError:
        return None


def _remember_awake_khz() -> int:
    # cpuinfo_max_freq, not the current cap. Sleep has often already lowered that.
    global _awake_khz
    if _awake_khz is None:
        _awake_khz = _read_khz(
            "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
        ) or 2_400_000
    return _awake_khz


def _sleep_khz() -> int:
    mins = [
        value
        for path in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_min_freq"))
        if (value := _read_khz(path))
    ]
    return min(mins) if mins else 1_500_000


def _set_cpu_max_khz(khz: int) -> None:
    global _cpu_clock_broken
    if _cpu_clock_broken:
        return
    path = _cpu_max_path()
    if path is None or _read_khz(path) == khz:
        return
    payload = f"{khz}\n".encode()
    try:
        try:
            with open(path, "wb") as fh:
                fh.write(payload)
        except OSError:
            # -n: a password prompt here blocks the service forever.
            result = subprocess.run(
                ["sudo", "-n", "tee", path],
                input=payload,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                check=False,
                timeout=2,
                start_new_session=True,
            )
            if result.returncode != 0:
                _cpu_clock_broken = True
                err = result.stderr.decode(errors="replace").strip()
                print(f"[cpu] could not set max clock to {khz // 1000} MHz: {err}", flush=True)
                return
        print(f"[cpu] max clock {khz // 1000} MHz", flush=True)
    except Exception as exc:
        _cpu_clock_broken = True
        print(f"[cpu] could not set max clock to {khz // 1000} MHz: {exc}", flush=True)


def _enter_sleep() -> None:
    global _deaf_until
    _set_cpu_max_khz(_sleep_khz())
    if wake_model is not None:
        wake_model.reset()
    wake_rec.Reset()
    sleep_rec.Reset()
    with q.mutex:
        q.queue.clear()
    _deaf_until = time.time() + 3.0


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
    global _awake_since
    try:
        item = q.get(timeout=0.2)
        data = item[1] if isinstance(item, tuple) else item
    except queue.Empty:
        return False

    if not data:
        return False

    if config.WAKE_BACKEND == "model":
        if time.time() < _deaf_until:
            return False
        score = wake_model.push_48k(data)
        if score is None or score < config.WAKE_THRESHOLD:
            if score is not None and score >= config.WAKE_LOG_THRESHOLD:
                print(f"[wake] ignored score={score:.2f}", flush=True)
            return False
        print(f"[wake] woke score={score:.2f}", flush=True)
        _set_cpu_max_khz(_remember_awake_khz())
        lights.set_color("idle")
        greet(lights, None, q)
        _awake_since = time.time()
        config.AWAKE = True
        config.CPU_MODE = True
        return True

    if not wake_rec.AcceptWaveform(data):
        return False

    result = json.loads(wake_rec.Result())
    text = result.get("text", "").lower().strip()

    score = _phrase_confidence(result.get("result", []), config.WAKE_PHRASE)
    if score is None:
        return False

    if score < config.WAKE_MIN_CONFIDENCE:
        print(f"[wake] ignored {text!r} conf={score:.2f}", flush=True)
        return False

    print(f"[wake] woke on {text!r} conf={score:.2f}", flush=True)
    _set_cpu_max_khz(_remember_awake_khz())
    lights.set_color("idle")
    greet(lights, None, q)
    _awake_since = time.time()
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


def _decode_theme() -> str | None:
    """Re-decode the last few seconds against theme names and return the theme key.

    The window never reaches back past the moment he finished greeting, so the
    wake phrase and his own voice are not in it.
    """
    cutoff = max(time.time() - config.THEME_AUDIO_SECONDS, _awake_since)
    blocks = [data for timestamp, data in list(_recent_audio) if timestamp >= cutoff]
    if not blocks:
        return None

    words: list[dict[str, Any]] = []
    for data in blocks:
        if theme_rec.AcceptWaveform(data):
            words += json.loads(theme_rec.Result()).get("result", [])
    words += json.loads(theme_rec.FinalResult()).get("result", [])
    theme_rec.Reset()

    spoken = [word.get("word", "") for word in words]
    matches: list[tuple[int, str]] = []
    i = 0
    while i < len(spoken):
        for size in (3, 2, 1):
            phrase = " ".join(spoken[i:i + size])
            if i + size <= len(spoken) and phrase in config.THEME_PHRASES:
                matches.append((i, config.THEME_PHRASES[phrase]))
                i += size
                break
        else:
            i += 1

    # Other speech in the window gets force-fitted onto themes too ("news for the
    # city" came back as "osaka"), so prefer the theme right after "lights".
    intent_positions = [
        pos for pos, word in enumerate(spoken) if word in config.LIGHTS_INTENT_WORDS
    ]
    after_intent = [
        theme for pos, theme in matches
        if intent_positions and pos > intent_positions[-1]
    ]
    if after_intent:
        theme = after_intent[0]
    elif matches:
        theme = matches[-1][1]
    else:
        theme = None

    print(f"[lights] theme grammar heard {' '.join(spoken)!r} -> {theme}", flush=True)
    return theme


def _grammar_hears_sleep() -> bool:
    cutoff = max(time.time() - 4.0, _awake_since)
    blocks = [data for timestamp, data in list(_recent_audio) if timestamp >= cutoff]
    if not blocks:
        return False

    words: list[dict[str, Any]] = []
    try:
        for data in blocks:
            if sleep_rec.AcceptWaveform(data):
                words += json.loads(sleep_rec.Result()).get("result", [])
        words += json.loads(sleep_rec.FinalResult()).get("result", [])
    finally:
        sleep_rec.Reset()

    spoken = " ".join(word.get("word", "") for word in words)
    heard = _is_sleep_request(spoken)
    if heard:
        print(f"[wake] sleep grammar heard {spoken!r}", flush=True)
    return heard


def _is_query(text: str) -> bool:
    return len(text) > 7 and len(text.split()) > 1


def _split_lights_clause(text: str) -> tuple[str, str]:
    """Split an utterance into its lights clause and everything else.

    "turn the lights on to fairfax and give me the weather" gives
    ("turn the lights on to fairfax", "give me the weather"). The last clause
    naming the lights wins, since earlier ones can be chatter misheard as "lights".
    """
    clauses = re.split(r"\s+(?:and then|and|then)\s+", text)
    for index in range(len(clauses) - 1, -1, -1):
        if set(clauses[index].split()) & config.LIGHTS_INTENT_WORDS:
            rest = clauses[:index] + clauses[index + 1:]
            return clauses[index], " and ".join(rest)
    return "", text


def _handle_lights_locally(text: str, lights: LightsLike) -> bool:
    """Handle a lights request without the LLM when it can be resolved here.

    Returns False, leaving it to the LLM, when no theme was heard.
    """
    global _awake_since
    tokens = set(text.split())
    if not tokens & config.LIGHTS_INTENT_WORDS:
        return False

    if "off" in tokens:
        print(f"[lights] local off from {text!r}", flush=True)
        action, theme = turn_off_lights, None
    else:
        theme = _decode_theme()
        if theme is None:
            return False
        print(f"[lights] local on {theme} from {text!r}", flush=True)
        action = turn_on_lights

    config.BUSY = True
    try:
        action(lights, theme)
    finally:
        config.BUSY = False
        _awake_since = time.time()
    return True


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

        if _is_sleep_request(full_text) or _grammar_hears_sleep():
            print(f"[wake] sleep request from {full_text!r}", flush=True)
            if config.CPU_MODE:
                play_audio("investigations_over")
            sleep(lights)
            return True

        lights_clause, rest = _split_lights_clause(full_text)
        if lights_clause and _handle_lights_locally(lights_clause, lights):
            if not _is_query(rest):
                return True
            print(f"[lights] passing rest to LLM: {rest!r}", flush=True)
            full_text = rest

        is_query = _is_query(full_text)

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
    was_awake = False

    try:
        _remember_awake_khz()
        _set_cpu_max_khz(_sleep_khz())
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
                    if was_awake:
                        _enter_sleep()
                        was_awake = False
                    if process_sleep_mode(q, wake_rec, lights):
                        last_command_time = time.time()
                        was_awake = True
                else:
                    was_awake = True
                    command_processed = process_awake_mode(lights, q, rec)
                    if command_processed:
                        last_command_time = time.time()

                    awake_time = 25 if config.CPU_MODE else 15
                    if config.AWAKE and (time.time() - last_command_time > awake_time):
                        sleep(lights)

    except Exception as e:
        throw_error(lights, e)
    finally:
        _set_cpu_max_khz(_remember_awake_khz())
        gc.collect()
