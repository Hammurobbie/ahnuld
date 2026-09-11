from __future__ import annotations

import os
import time
import asyncio
from typing import Any

from pywizlight import wizlight, PilotBuilder
from audio import play_audio, text_to_speech
from lights.hue_api import (
    rgb_to_xy,
    set_light_state,
    get_all_light_ids,
    get_light_ids_by_name,
    activate_scene,
)

# Bulbs are named rather than numbered throughout, and resolved to bridge IDs at
# call time by _ids(), so renumbering can't strand a theme on a light that's gone.

# Dimmed low in video mode so they don't compete with the screen.
THEATER_LIGHTS = ("Kitchen", "Desk", "Bathroom")

# Two-color themes walk the bulbs in this order, alternating rgb/rgb2. The Wiz
# bulb is the last position, so it picks up whichever color comes next.
ALTERNATING_ORDER = ("Bathroom", "Kitchen", "Clock", "Bookshelf", "Desk")

# The bathroom is a utility room, so themes run it at full brightness. read
# (uniform across bulbs), sleep (everything off), and videomode (dimmed with the
# other theater bulbs) deliberately opt out.
FULL_BRIGHT_LIGHTS = ("Bathroom",)
FULL_BRI = 254

# Per-bulb cinema levels, matching what was dialed in by hand on the bridge.
CINEMA_BRIGHTNESS = {
    "Bookshelf": 1,
    "Kitchen":   25,
    "Desk":      1,
    "Bathroom":  FULL_BRI,
    "Clock":     16,
}

SCENE_THEMES = {
    "fairfax":          "K0mIvJNac9-6CnL",
    "snowday":          "MZejKTLSy-cZsn4f",
    "moonlight":        "1ofOoEOk2gavw0BN",
    "ibiza":            "FRYZyq4vHCy6fNqg",
    "osaka":            "1advVnvQsMVBKcJd",
    "dreamydusk":       "k1AQMyRm1jmxpQaZ",
    "singapore":        "nmUphMMPpDa3220I",
    "galaxy":           "6btFza2Zi46dH09",
    "tokyo":            "C6zGdPF-UtFxn6N",
    "lavalamp":         "WbJ9oaRrFRnbuBDt",
    "tropicaltwilight": "rznRLrtElFILPTn",
    "boston":           "1-XWXVGx-fOvIg-G",
    "frost":            "CWrXxuSspVJUSFRB",
}

COLOR_THEMES = {
    "midnightinparis": {"rgb": (200, 50, 0),   "bri": 125},
    "moonrisekingdom": {"rgb": (200, 50, 0),   "bri": 254},
    "speakeasy":       {"rgb": (245, 112, 0),  "bri": 223},
    "prestige":        {"rgb": (200, 80, 20),  "bri": 255},
    "shmash":          {"rgb": (220, 50, 0),   "rgb2": (220, 50, 0),   "bri": 100, "lights": ALTERNATING_ORDER},
    "cherryblossom":   {"rgb": (200, 80, 40),  "rgb2": (250, 50, 50),  "bri": 175, "lights": ALTERNATING_ORDER},
    "cyberpunk":       {"rgb": (250, 0, 80),   "rgb2": (0, 220, 252),  "bri": 254, "lights": ALTERNATING_ORDER},
    "bladerunner":     {"rgb": (255, 60, 0),   "rgb2": (0, 200, 250),  "bri": 254, "lights": ALTERNATING_ORDER},
    "alien":           {"rgb": (0, 128, 0),    "rgb2": (255, 255, 1),  "bri": 254, "lights": ALTERNATING_ORDER},
    "godfather":       {"rgb": (250, 0, 0),    "rgb2": (255, 55, 1),   "bri": 120, "lights": ALTERNATING_ORDER},
    "brucealmighty":   {"rgb": (250, 250, 250),"rgb2": (250, 250, 250),"bri": 255, "lights": ALTERNATING_ORDER},
    "titanic":         {"rgb": (0, 0, 250),    "rgb2": (0, 50, 250),   "bri": 120, "lights": ALTERNATING_ORDER},
}

WIZ_FALLBACK_RGB = (245, 112, 0)
WIZ_FALLBACK_BRI = 223
# pywizlight clamps dimming to a 10% hardware floor, so any low value bottoms out.
# Must stay non-zero: _set_wiz_bulbs treats a falsy brightness as "nothing to do".
WIZ_MIN_BRI = 1


def _ids(names: tuple[str, ...]) -> list[str]:
    by_name = get_light_ids_by_name()
    return [by_name[n.lower()] for n in names if n.lower() in by_name]


def _alternating_color(
    position: int,
    rgb: tuple[int, ...],
    rgb2: tuple[int, ...],
) -> tuple[int, ...]:
    return rgb2 if position % 2 else rgb


def _apply_alternating_colors(
    light_ids: list[str],
    rgb: tuple[int, ...],
    rgb2: tuple[int, ...],
    bri: int,
    dim_ids: set[str] | None = None,
) -> None:
    full_ids = set(_ids(FULL_BRIGHT_LIGHTS))

    for i, light_id in enumerate(light_ids):
        state: dict[str, Any] = {
            "on": True,
            "bri": bri,
            "xy": rgb_to_xy(*_alternating_color(i, rgb, rgb2)),
        }

        if light_id in full_ids:
            state["bri"] = FULL_BRI
        # Video mode's dimming outranks the full-brightness rule.
        if dim_ids and light_id in dim_ids:
            state["bri"] = 25

        set_light_state(light_id, state)
        time.sleep(0.25)


async def _set_wiz_bulbs(
    bulbs: list[Any],
    rgb: tuple[int, ...] | None = None,
    brightness: int | None = None,
) -> None:
    try:
        if rgb and brightness:
            pb = PilotBuilder(rgb=rgb, brightness=brightness)
        elif brightness:
            pb = PilotBuilder(brightness=brightness)
        else:
            return
        await asyncio.gather(*(bulb.turn_on(pb) for bulb in bulbs), return_exceptions=True)
    except Exception:
        pass


async def activate_theme(
    theme: str | None,
    led_lights: Any = None,
) -> None:
    wiz_ips = [ip.strip() for ip in os.environ.get("WIZ_BULB_IPS", "").split(",") if ip.strip()]
    bulbs = [wizlight(ip) for ip in wiz_ips]

    async def _close_bulbs() -> None:
        await asyncio.gather(*(b.async_close() for b in bulbs), return_exceptions=True)

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

    try:
        if theme == "sleep":
            for hue_id in get_all_light_ids():
                set_light_state(hue_id, {"on": False})
            success()
            return

        if theme == "read":
            for hue_id in get_all_light_ids():
                set_light_state(hue_id, {"on": True, "bri": 120, "xy": [0.57, 0.412]})
            success()
            return

        if theme == "cinema":
            by_name = get_light_ids_by_name()
            for name, bri in CINEMA_BRIGHTNESS.items():
                hue_id = by_name.get(name.lower())
                if hue_id:
                    set_light_state(hue_id, {"on": True, "bri": bri})
            await _set_wiz_bulbs(bulbs, brightness=WIZ_MIN_BRI)
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
            _apply_alternating_colors(
                _ids(ALTERNATING_ORDER), rgb, rgb2, 75, dim_ids=set(_ids(THEATER_LIGHTS))
            )
            await _set_wiz_bulbs(bulbs, brightness=20)
            success()
            return

        # --- Scene themes (Hue Bridge scenes) ---

        if theme in SCENE_THEMES:
            activate_scene(SCENE_THEMES[theme])
            # Scenes cover the whole group, so re-assert full brightness after.
            for hue_id in _ids(FULL_BRIGHT_LIGHTS):
                set_light_state(hue_id, {"on": True, "bri": FULL_BRI})
            await _set_wiz_bulbs(bulbs, rgb=WIZ_FALLBACK_RGB, brightness=WIZ_FALLBACK_BRI)
            success()
            return

        # --- Color themes ---

        if theme in COLOR_THEMES:
            cfg_theme: Any = COLOR_THEMES[theme]
            rgb_cfg: tuple[int, ...] = cfg_theme["rgb"]
            rgb2_cfg: tuple[int, ...] | None = cfg_theme.get("rgb2")
            bri_cfg: int = cfg_theme["bri"]
            bulb_names: tuple[str, ...] | None = cfg_theme.get("lights")

            if bulb_names:
                hue_ids = _ids(bulb_names)
                alt_rgb2 = rgb2_cfg or rgb_cfg
                _apply_alternating_colors(hue_ids, rgb_cfg, alt_rgb2, bri_cfg)
                # The Wiz bulb is the next position after the Hue bulbs.
                wiz_rgb = _alternating_color(len(hue_ids), rgb_cfg, alt_rgb2)
            else:
                xy = rgb_to_xy(*rgb_cfg)
                full_ids = set(_ids(FULL_BRIGHT_LIGHTS))
                for lid in get_all_light_ids():
                    lid_bri = FULL_BRI if lid in full_ids else bri_cfg
                    set_light_state(lid, {"on": True, "bri": lid_bri, "xy": xy})
                wiz_rgb = rgb_cfg

            await _set_wiz_bulbs(bulbs, rgb=wiz_rgb, brightness=bri_cfg)
            success()
            return

        error()
    finally:
        await _close_bulbs()


if __name__ == "__main__":
    import sys
    _theme = sys.argv[1] if len(sys.argv) > 1 else ""
    asyncio.run(activate_theme(_theme))
