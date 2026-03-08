"""
Native tool definitions and executor for the learning computer agent.
Tools are exposed to Groq as function definitions; execution runs here (MCP fallback).
"""
import ast
import logging
import os
import re
import resource
import shlex
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import requests

import commands.config as config
from text_to_speech import text_to_speech
from commands.actions import turn_on_lights, turn_off_lights, sleep

NATIVE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current date and time (returns 12-hour format like 'Feb 28, 11:17 PM'). Use when the user asks what time or date it is.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather and today's forecast. Use when the user asks about weather, temperature, rain, or what to wear.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information, news, facts, or anything the user asks that you don't know. Returns top results with titles and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": "Set a countdown timer. Plays an alert sound when done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Number of seconds to count down.",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label for the timer (e.g. 'pasta', 'laundry').",
                    },
                },
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_light_themes",
            "description": "List available light theme names. Returns a comma-separated list. Use when the user asks for themes or before setting lights.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_lights",
            "description": "Turn lights on (optional theme), off, or set theme. Use get_light_themes for theme names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Turn lights on or off.",
                    },
                    "theme": {
                        "type": "string",
                        "description": "Optional theme name when turning on (e.g. cinema, read, sleep).",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_script",
            "description": "Write a Python script and save it to the sandbox directory. Use when the user asks you to write, create, or generate a Python function or program. The code you provide is saved to a .py file that can later be executed with execute_script. Scripts may ONLY use the Python standard library (e.g. math, random, json, datetime, re, collections, sys). Use sys.argv to read command-line arguments when the user provides values (execute_script has an 'args' parameter for this). Do NOT use third-party packages like yfinance, pandas, psutil, requests. No open(), exec(), eval(). Compute and print only. After calling this tool, do not read code aloud; only confirm save success briefly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the .py file to create (e.g. 'fibonacci.py'). Must end in .py and contain no path separators.",
                    },
                    "code": {
                        "type": "string",
                        "description": "The full Python source code to write to the file.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional one-line description of what the script does. Stored as a comment header.",
                    },
                },
                "required": ["filename", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_script",
            "description": "Run a Python script from the sandbox directory and return its output. Use after generate_script to test or run a script. Times out after 30 seconds. Do not recite code; summarize only the execution result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the .py file to execute (e.g. 'fibonacci.py').",
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional space-separated command-line arguments to pass to the script.",
                    },
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_scripts",
            "description": "List all Python scripts currently saved in the sandbox directory. Returns filenames and sizes. Use to see what scripts are available before executing. Read out the list for the user.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _get_time(arguments: dict, lights, q) -> tuple[str, bool]:
    now = datetime.now()
    h = now.hour % 12 or 12
    text = f"{now.strftime('%b %d')}, {h:02d}:{now.minute:02d} {'PM' if now.hour >= 12 else 'AM'}"
    return text, False


def _get_weather(arguments: dict, lights, q) -> tuple[str, bool]:
    lat = float(os.environ.get("LOCATION_LAT", "0"))
    lon = float(os.environ.get("LOCATION_LON", "0"))
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,apparent_temperature,weathercode,windspeed_10m,precipitation"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
        f"&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch"
        f"&timezone=America/New_York&forecast_days=1"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    c = data["current"]
    d = data["daily"]

    wmo_descriptions = {
        0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 48: "icy fog", 51: "light drizzle", 53: "drizzle",
        55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
        71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
        80: "light showers", 81: "showers", 82: "heavy showers",
        85: "snow showers", 86: "heavy snow showers",
        95: "thunderstorm", 96: "thunderstorm with hail", 99: "heavy thunderstorm",
    }
    condition = wmo_descriptions.get(c["weathercode"], f"code {c['weathercode']}")

    location_name = os.environ.get("LOCATION_NAME", "Local")
    result = (
        f"{location_name}: {c['temperature_2m']} degrees (feels like {c['apparent_temperature']} degrees), "
        f"{condition}, wind {c['windspeed_10m']} miles per hour, precipitation {c['precipitation']} inches. "
        f"Today's high {d['temperature_2m_max'][0]} degrees, low {d['temperature_2m_min'][0]} degrees, "
        f"total precipitation {d['precipitation_sum'][0]} inches."
    )
    return result, False


def _web_search(arguments: dict, lights, q) -> tuple[str, bool]:
    query = arguments.get("query", "").strip()
    if not query:
        return "No query provided.", False

    try:
        from ddgs import DDGS

        results = list(DDGS().text(query, max_results=5, backend="duckduckgo"))
    except Exception as e:
        return f"Search failed: {e}", False

    if not results:
        return "No results found.", False

    snippets = []
    for r in results[:4]:
        title = r.get("title", "")
        body = r.get("body", "")
        if title or body:
            snippets.append(f"{title}: {body}")

    return " | ".join(snippets) if snippets else "No useful results.", False


def _set_timer(arguments: dict, lights, q) -> tuple[str, bool]:
    seconds = int(arguments.get("seconds", 0))
    label = arguments.get("label", "timer").strip() or "timer"
    if seconds <= 0:
        return "Invalid timer duration.", False

    def _fire():
        threading.Event().wait(seconds)
        text_to_speech(f"Your {label} timer is done.")

    threading.Thread(target=_fire, daemon=True).start()

    mins, secs = divmod(seconds, 60)
    duration = f"{mins}m {secs}s" if mins else f"{secs}s"
    return f"Timer '{label}' set for {duration}.", False


def _get_light_themes(arguments: dict, lights, q) -> tuple[str, bool]:
    themes = ", ".join(config.KNOWN_THEMES)
    return themes, False


def _set_lights(arguments: dict, lights, q) -> tuple[str, bool]:
    action = (arguments.get("action") or "on").lower().strip()
    raw_theme = (arguments.get("theme") or "").strip() or None

    theme = None
    if raw_theme:
        normalized = raw_theme.lower().replace(" ", "").replace("-", "").replace("_", "")
        if normalized in config.KNOWN_THEMES:
            theme = normalized
        else:
            from thefuzz import fuzz
            best_theme = None
            highest_score = 0
            for known in config.KNOWN_THEMES:
                score = fuzz.ratio(normalized, known)
                if score > highest_score and score >= 70:
                    best_theme = known
                    highest_score = score
            theme = best_theme or normalized

    if action == "off":
        turn_off_lights(lights)
        return "Lights are off.", False
    turn_on_lights(lights, theme)
    if theme:
        return f"Lights set to {theme}.", False
    return "Lights are on.", False


SANDBOX_DIR = Path(__file__).resolve().parent.parent / "sandbox"
_SANDBOX_USER = "sandbox-runner"
_SANDBOX_PYTHON = "/usr/bin/python3"
_MAX_OUTPUT_CHARS = 2000
_EXEC_TIMEOUT_SECS = 30

_ALLOWED_IMPORTS = frozenset({
    "array", "bisect", "calendar", "cmath", "collections", "copy", "datetime",
    "decimal", "fractions", "functools", "heapq", "itertools", "json", "math",
    "numbers", "operator", "random", "re", "statistics", "string", "sys", "typing",
})
_BLOCKED_BUILTINS = {"exec", "eval", "compile", "__import__", "open"}
_BLOCKED_REGEX_PATTERNS = (
    r"__import__\s*\(",
)


def _validate_sandbox_filename(filename: str) -> str | None:
    """Return an error message if filename is unsafe, else None."""
    if not filename:
        return "No filename provided."
    if "/" in filename or "\\" in filename or ".." in filename:
        return "Invalid filename: path separators and '..' are not allowed."
    if not filename.endswith(".py"):
        return "Filename must end in .py"
    if len(filename) > 128:
        return "Filename too long (max 128 characters)."
    return None


def _audit_code(code: str) -> str | None:
    """Return an error string if code contains blocked behavior, otherwise None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Invalid Python syntax: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".", 1)[0]
                if module not in _ALLOWED_IMPORTS:
                    return f"Only standard library modules are allowed (e.g. math, random, json). '{module}' is not available in the sandbox."
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module not in _ALLOWED_IMPORTS:
                return f"Only standard library modules are allowed (e.g. math, random, json). '{module}' is not available in the sandbox."
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_BUILTINS:
                return f"Blocked call detected: {node.func.id}()"
            if isinstance(node.func, ast.Attribute) and node.func.attr in _BLOCKED_BUILTINS:
                return f"Blocked call detected: {node.func.attr}()"

    lowered = code.lower()
    for pattern in _BLOCKED_REGEX_PATTERNS:
        if re.search(pattern, lowered):
            return f"Blocked pattern detected: {pattern}"
    return None


def _sandbox_limits() -> None:
    mb = 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (128 * mb, 128 * mb))
    resource.setrlimit(resource.RLIMIT_CPU, (_EXEC_TIMEOUT_SECS, _EXEC_TIMEOUT_SECS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 * mb, 1 * mb))


def _generate_script(arguments: dict, lights, q) -> tuple[str, bool]:
    filename = (arguments.get("filename") or "").strip()
    code = arguments.get("code") or ""
    description = (arguments.get("description") or "").strip()

    err = _validate_sandbox_filename(filename)
    if err:
        return err, False

    if not code.strip():
        return "No code provided.", False

    if "\n" not in code and "\\n" in code:
        code = code.replace("\\n", "\n").replace("\\t", "\t")
    audit_error = _audit_code(code)
    if audit_error:
        return f"Security policy violation: {audit_error}", False

    try:
        SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        filepath = SANDBOX_DIR / filename

        header = f"# {description}\n" if description else ""
        filepath.write_text(header + code, encoding="utf-8")
        return f"Script saved to sandbox/{filename} ({len(code)} chars).", False
    except OSError as e:
        return f"File write error: {e}", False
    except Exception as e:
        return f"generate_script failed: {e}", False


def _execute_script(arguments: dict, lights, q) -> tuple[str, bool]:
    filename = (arguments.get("filename") or "").strip()
    extra_args = (arguments.get("args") or "").strip()

    err = _validate_sandbox_filename(filename)
    if err:
        return err, False

    filepath = SANDBOX_DIR / filename
    if not filepath.is_file():
        return f"Script not found: sandbox/{filename}", False

    cmd = [_SANDBOX_PYTHON, "-u", str(filepath)]
    if extra_args:
        cmd.extend(shlex.split(extra_args))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_EXEC_TIMEOUT_SECS,
            cwd=str(SANDBOX_DIR),
            preexec_fn=_sandbox_limits,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += ("\n--- stderr ---\n" if output else "--- stderr ---\n") + result.stderr

        if not output.strip():
            output = "(no output)"

        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + "\n... (truncated)"

        if result.returncode != 0:
            output = f"Exit code {result.returncode}\n{output}"

        return output, False
    except subprocess.TimeoutExpired:
        return f"Script timed out after {_EXEC_TIMEOUT_SECS} seconds.", False
    except OSError as e:
        return f"Execution error: {e}", False
    except Exception as e:
        return f"execute_script failed: {e}", False


def _list_scripts(arguments: dict, lights, q) -> tuple[str, bool]:
    try:
        if not SANDBOX_DIR.is_dir():
            return "No scripts found (sandbox directory does not exist yet).", False

        scripts = sorted(SANDBOX_DIR.glob("*.py"))
        if not scripts:
            return "No scripts found.", False

        lines = []
        for p in scripts:
            size = p.stat().st_size
            lines.append(f"  {p.name} ({size} bytes)")
        return "Scripts in sandbox/:\n" + "\n".join(lines), False
    except Exception as e:
        return f"list_scripts failed: {e}", False


_NATIVE_EXECUTORS = {
    "get_time": _get_time,
    "get_weather": _get_weather,
    "web_search": _web_search,
    "set_timer": _set_timer,
    "get_light_themes": _get_light_themes,
    "set_lights": _set_lights,
    "generate_script": _generate_script,
    "execute_script": _execute_script,
    "list_scripts": _list_scripts,
}


def execute_native_tool(name: str, arguments: dict, lights, q) -> tuple[str, bool]:
    """
    Execute a native tool by name. Returns (result_string, exit_cpu_mode).
    exit_cpu_mode is True only for go_to_sleep; caller should exit the agent loop.
    """
    if name not in _NATIVE_EXECUTORS:
        return f"Unknown native tool: {name}", False
    try:
        return _NATIVE_EXECUTORS[name](arguments, lights, q)
    except Exception as e:
        return f"Tool error: {str(e)}", False