from __future__ import annotations

import os
from typing import Any

from thefuzz import fuzz

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

# Spoken leftovers that are not themes. partial_ratio used to treat these as
# matches because they are substrings of real theme names: "the" is inside
# "godfather" at score 100, "to" inside "tokyo"/"boston", "set" inside "sunset".
# That is why a missed theme request sometimes slammed the room into Godfather.
THEME_STOPWORDS: frozenset[str] = frozenset({
    "a", "and", "light", "lights", "mode", "off", "on", "please",
    "put", "set", "the", "theme", "to", "turn",
})

THEME_ALIASES: dict[str, str] = {
    "tropicaltwilight": "sunset",
    "downtowndrizzle": "boston",
    "fuchsiafrost": "frost",
}

# How each theme is actually said, for the theme-only grammar that re-decodes a
# lights request. Every word must be in the Vosk model's vocabulary or Vosk drops
# it with a warning; "cyberpunk", "lavalamp", "snowday" and "shmash" are not, so
# they appear only as spelled-out forms.
THEME_PHRASES: dict[str, str] = {
    "sleep": "sleep",
    "read": "read",
    "reading": "read",
    "cinema": "cinema",
    "midnight in paris": "midnightinparis",
    "moonrise kingdom": "moonrisekingdom",
    "moon rise kingdom": "moonrisekingdom",
    "speakeasy": "speakeasy",
    "speak easy": "speakeasy",
    "smash": "shmash",
    "cherry blossom": "cherryblossom",
    "cyber punk": "cyberpunk",
    "blade runner": "bladerunner",
    "bladerunner": "bladerunner",
    "alien": "alien",
    "godfather": "godfather",
    "god father": "godfather",
    "bruce almighty": "brucealmighty",
    "titanic": "titanic",
    "prestige": "prestige",
    "fairfax": "fairfax",
    "fair fax": "fairfax",
    "moonlight": "moonlight",
    "moon light": "moonlight",
    "ibiza": "ibiza",
    "dreamy dusk": "dreamydusk",
    "osaka": "osaka",
    "singapore": "singapore",
    "galaxy": "galaxy",
    "tokyo": "tokyo",
    "lava lamp": "lavalamp",
    "sunset": "sunset",
    "sun set": "sunset",
    "tropical twilight": "sunset",
    "snow day": "snowday",
    "boston": "boston",
    "downtown drizzle": "boston",
    "frost": "frost",
    "fuchsia frost": "frost",
    "video mode": "videomode",
}

# The rest of a lights request, so those words land here instead of being
# force-fitted onto a theme. Without them "turn on the lights" alone would come
# back as whichever theme sounds closest.
THEME_GRAMMAR_FILLER: list[str] = [
    "hey", "arnold", "turn", "on", "off", "the", "lights", "light", "set",
    "to", "put", "in", "please", "change", "make", "it", "theme", "mode",
    "can", "you", "switch", "and", "a",
]

# Awake-mode words that mark an utterance as a lights request.
LIGHTS_INTENT_WORDS: frozenset[str] = frozenset({"light", "lights", "theme"})

# Seconds of recent audio re-decoded for a lights request, never reaching back
# past the end of his greeting.
THEME_AUDIO_SECONDS: float = 7.0


def match_light_theme(raw: str | None) -> str | None:
    """Return a known theme name, or None if this is not a real theme request."""
    if not raw:
        return None

    compact = raw.lower().replace("-", "").replace("_", "").replace(" ", "")
    if compact in THEME_ALIASES:
        return THEME_ALIASES[compact]
    if compact in KNOWN_THEMES:
        return compact

    tokens = [
        token for token in raw.lower().replace("-", " ").replace("_", " ").split()
        if token not in THEME_STOPWORDS
    ]
    cleaned = "".join(tokens)
    if not cleaned:
        return None
    if cleaned in THEME_ALIASES:
        return THEME_ALIASES[cleaned]
    if cleaned in KNOWN_THEMES:
        return cleaned

    for known in KNOWN_THEMES:
        if known in cleaned or cleaned in known and len(cleaned) >= 5:
            return known

    if len(cleaned) < 4:
        return None

    best_theme = None
    highest_score = 0
    for known in KNOWN_THEMES:
        score = fuzz.ratio(cleaned, known)
        if score > highest_score:
            best_theme = known
            highest_score = score
    return best_theme if highest_score >= 80 else None


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
