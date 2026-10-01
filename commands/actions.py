from __future__ import annotations

import os
import re
import sys
import time
import random
import asyncio
import queue
from typing import Any

import requests

import commands.config as config
from audio import play_audio, text_to_speech
from lights.turn_off_lights import main as kill_lights
from lights import activate_theme

from project_types import LightsLike

_MAX_TTS_ERROR_LEN = 160


def _humanize_error(error: Exception | str) -> str:
    # Friendly summaries for the network errors that actually fire here.
    if isinstance(error, requests.exceptions.ConnectionError):
        return "I can't reach the lights bridge. The IP may have changed."
    if isinstance(error, requests.exceptions.Timeout):
        return "The lights bridge timed out."
    if isinstance(error, requests.exceptions.HTTPError):
        code = getattr(getattr(error, "response", None), "status_code", None)
        return f"Lights bridge returned error {code}." if code else "Lights bridge returned an error."
    if isinstance(error, requests.exceptions.RequestException):
        return "Network error talking to the lights."

    msg = str(error)
    # Strip URLs and long opaque tokens (API keys, scene IDs) so TTS doesn't spell them out.
    msg = re.sub(r"https?://\S+", "", msg)
    msg = re.sub(r"/api/\S+", "", msg)
    msg = re.sub(r"\b[A-Za-z0-9_-]{20,}\b", "", msg)
    msg = re.sub(r"\s+", " ", msg).strip(" .,:;-")

    if not msg:
        msg = type(error).__name__ if isinstance(error, Exception) else "Unknown error"
    if len(msg) > _MAX_TTS_ERROR_LEN:
        msg = msg[: _MAX_TTS_ERROR_LEN - 1].rstrip() + "..."
    return msg


def throw_error(lights: LightsLike, error: Exception | str | None = None) -> None:
    if error is not None:
        text_to_speech(_humanize_error(error))
    else:
        play_audio("did_i_do_wrong")
    lights.set_color("error")
    lights.change_after(6, "idle")

def flush_queue(q: queue.Queue[Any]) -> None:
    while not q.empty():
        try:
            q.get_nowait()
        except Exception as e:
            break

def greet(
    lights: LightsLike,
    extra: Any = None,
    audio_queue: queue.Queue[Any] | None = None,
) -> None:
    if config.AWAKE:
        return
    try:
        options = ["hi", "howdy", "want"]
        play_audio(random.choice(options))
        from audio.play_audio import audio_queue as speaker_queue
        speaker_queue.join()
        if audio_queue:
            flush_queue(audio_queue)
    except Exception as e:
        throw_error(lights, e)

def turn_off_lights(lights: LightsLike, extra: Any = None) -> None:
    try:
        lights.set_color("thinking")
        asyncio.run(kill_lights())
        time.sleep(4)
        lights.set_color("success")
        lights.change_after(6, "idle")
    except Exception as e:
        throw_error(lights, e)

def turn_on_lights(lights: LightsLike, theme: str | None = None) -> None:
    try:
        asyncio.run(activate_theme(theme, led_lights=lights))
    except Exception as e:
        throw_error(lights, e)

def sleep(lights: LightsLike, extra: Any = None) -> None:
    try:
        lights.stop()
    except Exception as e:
        throw_error(lights, e)
    config.AWAKE = False
    config.CPU_MODE = False

def shut_down(lights: LightsLike, extra: Any = None) -> None:
    try:
        play_audio("hasta")
        lights.set_color("error")
        lights.change_after(6)
        sys.exit(0)
    except Exception as e:
        throw_error(lights, e)

def self_destruct(lights: LightsLike, extra: Any = None) -> None:
    try:
        options = ["bye", "hasta", "ill_be_back", "scream"]
        play_audio("count_down")
        lights.set_color("error")
        time.sleep(7)
        play_audio(random.choice(options))
        lights.stop()
        time.sleep(4)
        os.system("sudo shutdown now")
    except Exception as e:
        throw_error(lights, e)

def execute_command(
    command: dict[str, Any],
    lights: LightsLike,
    text: str,
) -> None:
    if config.BUSY:
        return
    config.BUSY = True
    try:
        func_name = command["func"]
        theme = None

        if command.get("args"):
            leftover = text.split(command["cmd"], 1)[-1].strip()
            # If the exact command string wasn't in the transcript, the split
            # returns the whole utterance. Still match against that leftover.
            theme = config.match_light_theme(leftover)
            if leftover and theme is None:
                tokens = [
                    token for token in leftover.lower().split()
                    if token not in config.THEME_STOPWORDS
                ]
                if tokens:
                    # Named something we could not resolve. Pass it through so
                    # activate_theme errors instead of guessing Godfather.
                    theme = leftover.replace(" ", "")
            if theme:
                print(f"[lights] matched {leftover!r} -> {theme}", flush=True)
            else:
                print(f"[lights] on with no theme (leftover={leftover!r})", flush=True)

        if func_name in globals():
            globals()[func_name](lights, theme)
        else:
            text_to_speech("I don't know that command.")
    except Exception as e:
        throw_error(lights, e)
    finally:
        config.BUSY = False
