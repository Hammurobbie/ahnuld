from __future__ import annotations

import os
from typing import Any

# Project root (config lives in commands/)
_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BUSY: bool = False
AWAKE: bool = False
CPU_MODE: bool = False
CPU_MODE_MAX_ITERATIONS: int = 8
CPU_MODE_HISTORY_TURNS: int = 2
CPU_MODE_PLAN_FIRST: bool = True
BLOCKSIZE: int = 8000
LISTENING: bool = True
SAMPLE_RATE: int = 48000
MIC_DEVICE_INDEX: int = 3
OUTPUT_DEVICE_INDEX: int = 2
VOSK_MODEL_PATH: str = os.path.join(_ROOT, "audio", "vosk-model-small-en-us-0.15")

# Sleep mode decodes against this restricted grammar instead of the full model.
# Vosk maps anything outside the list to [unk] and reports it as empty text, so
# unrelated speech can't wake him and quiet speech still resolves to the phrase.
WAKE_WORDS: list[str] = ["hey arnold"]

# Competing words, so conversation has somewhere to land other than the wake
# phrase. With only the phrase and [unk] in the grammar, meeting chatter was
# force-fitted onto "hey arnold" and reported at confidence 1.00 -- there was
# nothing for it to lose to, which made the confidence score meaningless. The
# first group are phonetic neighbours of "arnold"; the rest are just common
# speech. Matching still requires the whole phrase, so a decoy on its own is
# harmless.
WAKE_DECOYS: list[str] = [
    "arnold", "around", "although", "already", "all", "old", "hold", "told",
    "gold", "world", "another", "under", "aren't", "alone", "along",
    "hey", "hello", "okay", "yeah", "yes", "no", "and", "the", "a", "so",
    "but", "they", "there", "then", "that", "this", "it", "i", "we", "you",
    "what", "when", "how", "why", "who", "well", "just", "like", "know",
    "think", "going", "get", "got", "can", "will", "would", "should", "about",
    "with", "for", "from", "have", "has", "had", "right", "our", "are", "or",
    "her", "him", "them", "on", "in", "at", "to", "of", "was", "were",
]

# The full phrase has to appear. Surrounding [unk] is fine, since genuine wakes
# often decode as "[unk] hey arnold" or "hey hey arnold".
WAKE_PHRASE: str = "hey arnold"

# Floor on the per-word confidence of the matched phrase, as a backstop against
# garbage decodes only. It cannot be used to separate real wakes from false ones:
# logged accidents during meetings scored 1.00 while a confirmed intentional wake
# scored 0.68, so any floor high enough to cut the former loses the latter. The
# decoy vocabulary is what does that work. Kept just under the lowest real wake
# measured against the decoy grammar (0.45).
WAKE_MIN_CONFIDENCE: float = 0.40

KNOWN_THEMES: list[str] = [
    "sleep",
    "read",
    "cinema",
    "midnightinparis",
    "moonrisekingdom",
    "speakeasy",
    "shmash",
    "cherryblossom",
    "cyberpunk",
    "bladerunner",
    "alien",
    "godfather",
    "brucealmighty",
    "titanic",
    "prestige",
    "fairfax",
    "moonlight",
    "ibiza",
    "dreamydusk",
    "osaka",
    "singapore",
    "galaxy",
    "tokyo",
    "lavalamp",
    "sunset",
    "snowday",
    "boston",
    "frost",
    "videomode",
]

# MCP servers for learning computer (optional).
# Each entry: {"command": str, "args": list[str]}
# Example:
# MCP_SERVERS = [
#     {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/pi"]},
# ]
MCP_SERVERS: list[dict[str, Any]] = []

COMMANDS: list[dict[str, Any]] = [
    {"cmd": "hey arnold", "func": "greet", "args": False},
    {"cmd": "on the lights", "func": "turn_on_lights", "args": True},
    {"cmd": "off the lights", "func": "turn_off_lights", "args": False},
    {"cmd": "go to sleep", "func": "sleep", "args": False},
    {"cmd": "hasta la vista", "func": "shut_down", "args": False},
    {"cmd": "self destruct", "func": "self_destruct", "args": False},
]
