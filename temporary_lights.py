import os
import sys
import requests
import json
import time


BRIDGE_IP = os.environ.get("HUE_BRIDGE_IP", "")
USERNAME = os.environ.get("HUE_API_KEY", "")
ALLOWED_STATE_KEYS = {
    "on", "bri", "hue", "sat", "xy", "ct",
    "effect", "alert", "transitiontime"
}

def get_current_states():
    url = f"http://{BRIDGE_IP}/api/{USERNAME}/lights"
    lights = requests.get(url).json()

    prev_states = {}
    for light_id, info in lights.items():
        prev_states[light_id] = info["state"].copy()

    return prev_states


def activate_scene(theme):
    scene_id = "odfijW-SAEsETap" if theme == "bright" else theme
    url = f"http://{BRIDGE_IP}/api/{USERNAME}/groups/4/action"
    payload = {"on": True, "scene": scene_id}
    requests.put(url, json.dumps(payload))
    print(theme, scene_id)

def turn_off():
    urlG = f"http://{BRIDGE_IP}/api/{USERNAME}/lights/"
    responseG = requests.get(urlG)
    lights = json.loads(responseG.text)

    for light in lights:
        url = f'{urlG}{light}/state'
        payload = json.dumps({"on": False})
        requests.put(url, payload)


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

        if "effect" in state:
            filtered["effect"] = state["effect"]
        if "transitiontime" in state:
            filtered["transitiontime"] = state["transitiontime"]

        url = f"http://{BRIDGE_IP}/api/{USERNAME}/lights/{light_id}/state"
        requests.put(url, json.dumps(filtered))
