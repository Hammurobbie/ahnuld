"""
Native tool definitions and executor for the learning computer agent.
Tools are exposed to Groq as function definitions; execution runs here (MCP fallback).
"""
import os
import threading
from datetime import datetime

import requests

import commands.config as config
from text_to_speech import text_to_speech
from commands.actions import turn_on_lights, turn_off_lights, sleep

# Web search: free via ddgs (DuckDuckGo), no API key

# Groq tool definitions (OpenAI-compatible format)
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
        f"{location_name}: {c['temperature_2m']}°F (feels like {c['apparent_temperature']}°F), "
        f"{condition}, wind {c['windspeed_10m']} mph, precip {c['precipitation']} in. "
        f"Today's high {d['temperature_2m_max'][0]}°F / low {d['temperature_2m_min'][0]}°F, "
        f"total precip {d['precipitation_sum'][0]} in."
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


_NATIVE_EXECUTORS = {
    "get_time": _get_time,
    "get_weather": _get_weather,
    "web_search": _web_search,
    "set_timer": _set_timer,
    "get_light_themes": _get_light_themes,
    "set_lights": _set_lights,
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