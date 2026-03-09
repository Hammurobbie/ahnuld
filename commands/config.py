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
MIC_DEVICE_INDEX: int = 1
VAD_THRESHOLD: float = 0.03
VOSK_MODEL_PATH: str = os.path.join(_ROOT, "audio", "vosk-model-small-en-us-0.15")

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
    "tropicaltwilight",
    "snowday",
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
