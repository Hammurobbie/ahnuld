BUSY = False
AWAKE = False
CPU_MODE = False
CPU_MODE_MAX_ITERATIONS = 8
CPU_MODE_HISTORY_TURNS = 2
CPU_MODE_PLAN_FIRST = True
BLOCKSIZE = 8000
LISTENING = True
SAMPLE_RATE = 48000
MIC_DEVICE_INDEX = 1
VAD_THRESHOLD = 0.03
VOSK_MODEL_PATH = "vosk-model-small-en-us-0.15"

KNOWN_THEMES = [
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
MCP_SERVERS = []

COMMANDS = [
    {"cmd": "hey arnold", "func": "greet", "args": False},
    {"cmd": "on the lights", "func": "turn_on_lights", "args": True},
    {"cmd": "off the lights", "func": "turn_off_lights", "args": False},
    {"cmd": "go to sleep", "func": "sleep", "args": False},
    {"cmd": "hasta la vista", "func": "shut_down", "args": False},
    {"cmd": "self destruct", "func": "self_destruct", "args": False},
]
