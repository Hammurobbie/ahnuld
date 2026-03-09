import os
import json
import requests

_BRIDGE_IP = os.environ.get("HUE_BRIDGE_IP", "")
_API_KEY = os.environ.get("HUE_API_KEY", "")


def _base_url():
    return f"http://{_BRIDGE_IP}/api/{_API_KEY}"


def rgb_to_xy(r, g, b):
    X = r * 0.649926 + g * 0.103455 + b * 0.197109
    Y = r * 0.234327 + g * 0.743075 + b * 0.022598
    Z = r * 0.0 + g * 0.053077 + b * 1.035763
    total = X + Y + Z
    return [round(X / total, 4), round(Y / total, 4)]


def get_all_light_ids():
    return list(requests.get(f"{_base_url()}/lights").json().keys())


def set_light_state(light_id, state):
    requests.put(f"{_base_url()}/lights/{light_id}/state", json.dumps(state))


def set_all_lights(state):
    for light_id in get_all_light_ids():
        set_light_state(light_id, state)


def turn_off_all():
    set_all_lights({"on": False})


def activate_scene(scene_id, group=4):
    requests.put(
        f"{_base_url()}/groups/{group}/action",
        json.dumps({"on": True, "scene": scene_id}),
    )


def get_current_states():
    lights = requests.get(f"{_base_url()}/lights").json()
    return {lid: info["state"].copy() for lid, info in lights.items()}


def restore_states(prev_states):
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
