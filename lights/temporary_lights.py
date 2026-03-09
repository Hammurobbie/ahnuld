from __future__ import annotations

from lights.hue_api import (
    get_current_states,
    restore_states,
    turn_off_all as turn_off,
    activate_scene as _activate_scene,
)


def activate_scene(theme: str) -> None:
    scene_id = "odfijW-SAEsETap" if theme == "bright" else theme
    _activate_scene(scene_id)
