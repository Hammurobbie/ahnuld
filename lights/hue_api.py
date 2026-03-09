from __future__ import annotations

import os
import json
from typing import Any

import requests

_BRIDGE_IP: str = os.environ.get("HUE_BRIDGE_IP", "")
_API_KEY: str = os.environ.get("HUE_API_KEY", "")


def _base_url() -> str:
    return f"http://{_BRIDGE_IP}/api/{_API_KEY}"


def rgb_to_xy(r: int, g: int, b: int) -> list[float]:
    X = r * 0.649926 + g * 0.103455 + b * 0.197109
    Y = r * 0.234327 + g * 0.743075 + b * 0.022598
    Z = r * 0.0 + g * 0.053077 + b * 1.035763
    total = X + Y + Z
    return [round(X / total, 4), round(Y / total, 4)]


def get_all_light_ids() -> list[str]:
    return list(requests.get(f"{_base_url()}/lights").json().keys())


def set_light_state(light_id: str | int, state: dict[str, Any]) -> None:
    requests.put(f"{_base_url()}/lights/{light_id}/state", json.dumps(state))


def set_all_lights(state: dict[str, Any]) -> None:
    for light_id in get_all_light_ids():
        set_light_state(light_id, state)


def turn_off_all() -> None:
    set_all_lights({"on": False})


def activate_scene(scene_id: str, group: int = 4) -> None:
    requests.put(
        f"{_base_url()}/groups/{group}/action",
        json.dumps({"on": True, "scene": scene_id}),
    )


def get_current_states() -> dict[str, Any]:
    lights = requests.get(f"{_base_url()}/lights").json()
    return {lid: info["state"].copy() for lid, info in lights.items()}


def restore_states(prev_states: dict[str, Any]) -> None:
    for light_id, state in prev_states.items():
        filtered = {}

        if "on" in state:
            filtered["on"] = state["on"]
        if "bri" in state:
            filtered["bri"] = state["bri"]

        colormode = state.get("colormode")
        if colormode == "xy" and "xy" in state:
            filtered["xy"] = state["xy"]
        elif colormode == "ct" and "ct" in state:
            filtered["ct"] = state["ct"]
        elif colormode == "hs" and "hue" in state and "sat" in state:
            filtered["hue"] = state["hue"]
            filtered["sat"] = state["sat"]

        for key in ("effect", "transitiontime"):
            if key in state:
                filtered[key] = state[key]

        set_light_state(light_id, filtered)
