import os
import time
import asyncio

from pywizlight import wizlight, PilotBuilder
from audio import play_audio, text_to_speech
from lights.hue_api import rgb_to_xy, set_light_state, get_all_light_ids, activate_scene

ALL_LIGHTS = list(range(1, 15))
THEATER_LIGHTS = [5, 6, 7, 13, 14]
STANDARD_LIGHTS = [7, 1, 2, 4, 3, 5, 6, 8, 10, 9, 11, 12, 13, 14]

SCENE_THEMES = {
    "fairfax":     "K0mIvJNac9-6CnL",
    "snowday":     "MZejKTLSy-cZsn4f",
    "moonlight":   "1ofOoEOk2gavw0BN",
    "ibiza":       "FRYZyq4vHCy6fNqg",
    "osaka":       "1advVnvQsMVBKcJd",
    "dreamydusk":  "k1AQMyRm1jmxpQaZ",
    "singapore":   "nmUphMMPpDa3220I",
    "galaxy":      "6btFza2Zi46dH09",
    "tokyo":       "C6zGdPF-UtFxn6N",
    "lavalamp":    "WbJ9oaRrFRnbuBDt",
}

COLOR_THEMES = {
    "midnightinparis": {"rgb": (200, 50, 0),   "bri": 125},
    "moonrisekingdom": {"rgb": (200, 50, 0),   "bri": 254},
    "speakeasy":       {"rgb": (245, 112, 0),  "bri": 223},
    "prestige":        {"rgb": (200, 80, 20),  "bri": 255},
    "shmash":          {"rgb": (220, 50, 0),   "rgb2": (220, 50, 0),   "bri": 100, "lights": ALL_LIGHTS},
    "cherryblossom":   {"rgb": (200, 80, 40),  "rgb2": (250, 50, 50),  "bri": 175, "lights": STANDARD_LIGHTS},
    "cyberpunk":       {"rgb": (250, 0, 80),   "rgb2": (0, 220, 252),  "bri": 254, "lights": STANDARD_LIGHTS},
    "bladerunner":     {"rgb": (255, 60, 0),   "rgb2": (0, 200, 250),  "bri": 254, "lights": STANDARD_LIGHTS},
    "alien":           {"rgb": (0, 128, 0),    "rgb2": (255, 255, 1),  "bri": 254, "lights": STANDARD_LIGHTS},
    "godfather":       {"rgb": (250, 0, 0),    "rgb2": (255, 55, 1),   "bri": 120, "lights": STANDARD_LIGHTS},
    "brucealmighty":   {"rgb": (250, 250, 250),"rgb2": (250, 250, 250),"bri": 255, "lights": ALL_LIGHTS},
    "titanic":         {"rgb": (0, 0, 250),    "rgb2": (0, 50, 250),   "bri": 120, "lights": ALL_LIGHTS},
}

WIZ_FALLBACK_RGB = (245, 112, 0)
WIZ_FALLBACK_BRI = 223


def _apply_alternating_colors(lights, rgb, rgb2, bri, video_mode=False):
    xy1 = rgb_to_xy(*rgb)
    xy2 = rgb_to_xy(*rgb2)
    pay1 = {"on": True, "bri": bri, "xy": xy1}
    pay2 = {"on": True, "bri": bri, "xy": xy2}

    for i, light_id in enumerate(lights):
        state = pay2.copy() if (i % 2) else pay1.copy()

        if video_mode:
            if light_id == 1:
                state = {"on": False}
            elif light_id in THEATER_LIGHTS:
                state["bri"] = 25

        set_light_state(light_id, state)
        time.sleep(0.25)


async def _set_wiz_bulbs(bulbs, rgb=None, brightness=None):
    try:
        if rgb and brightness:
            pb = PilotBuilder(rgb=rgb, brightness=brightness)
        elif brightness:
            pb = PilotBuilder(brightness=brightness)
        else:
            return
        await asyncio.gather(*(bulb.turn_on(pb) for bulb in bulbs))
    except Exception:
        pass


async def activate_theme(theme, led_lights=None):
    wiz_ips = [ip.strip() for ip in os.environ.get("WIZ_BULB_IPS", "").split(",") if ip.strip()]
    bulbs = [wizlight(ip) for ip in wiz_ips]

    is_video_mode = theme == "videomode"

    if led_lights and not is_video_mode:
        led_lights.set_color("thinking")

    def success():
        if led_lights:
            led_lights.set_color("success")
            led_lights.change_after(6, "idle")
            time.sleep(2)

    def error():
        if led_lights:
            led_lights.set_color("error")
            led_lights.change_after(6, "idle")
        text_to_speech("I couldn't set that light theme.")
        time.sleep(2)

    # --- Special themes with custom per-light logic ---

    if theme == "sleep":
        for hue_id in [2, 4, 8, 10]:
            set_light_state(hue_id, {"on": False})
        success()
        return

    if theme == "read":
        for hue_id in [2, 4, 8, 10]:
            set_light_state(hue_id, {"on": True, "bri": 120, "xy": [0.57, 0.412]})
        for hue_id in [8, 10]:
            set_light_state(hue_id, {"on": False})
        success()
        return

    if theme == "cinema":
        set_light_state(1, {"on": False})
        for hue_id in THEATER_LIGHTS:
            set_light_state(hue_id, {"on": True, "bri": 25})
        for hue_id in [2, 4, 3, 8, 10, 9, 11, 12]:
            set_light_state(hue_id, {"on": True, "bri": 75})
        await _set_wiz_bulbs(bulbs, brightness=20)
        success()
        return

    if is_video_mode:
        if led_lights:
            led_lights.stop()
        from utils.capture_environmental_colors import capture_environmental_colors
        colors = capture_environmental_colors()
        if not colors or len(colors) < 2:
            error()
            return
        rgb = tuple(colors[0])
        rgb2 = tuple(colors[1])
        _apply_alternating_colors(STANDARD_LIGHTS, rgb, rgb2, 75, video_mode=True)
        await _set_wiz_bulbs(bulbs, brightness=20)
        success()
        return

    # --- Scene themes (Hue Bridge scenes) ---

    if theme in SCENE_THEMES:
        activate_scene(SCENE_THEMES[theme])
        await _set_wiz_bulbs(bulbs, rgb=WIZ_FALLBACK_RGB, brightness=WIZ_FALLBACK_BRI)
        success()
        return

    # --- Color themes ---

    if theme in COLOR_THEMES:
        cfg = COLOR_THEMES[theme]
        rgb = cfg["rgb"]
        rgb2 = cfg.get("rgb2")
        bri = cfg["bri"]
        lights = cfg.get("lights")

        if lights:
            _apply_alternating_colors(lights, rgb, rgb2 or rgb, bri)
        else:
            xy = rgb_to_xy(*rgb)
            for lid in get_all_light_ids():
                set_light_state(lid, {"on": True, "bri": bri, "xy": xy})

        await _set_wiz_bulbs(bulbs, rgb=rgb, brightness=bri)
        success()
        return

    error()


if __name__ == "__main__":
    import sys
    _theme = sys.argv[1] if len(sys.argv) > 1 else ""
    asyncio.run(activate_theme(_theme))
