from __future__ import annotations

import time

from gpiozero import MotionSensor

from project_types import LightsLike


def detect_motion(lights: LightsLike) -> bool:
    pir = MotionSensor(17)
    start = time.time()

    try:
        while True:
            if lights.is_stopped():
                lights.set_color("idle")

            try:
                pir.wait_for_motion(timeout=0.2)
            except TimeoutError:
                pass
            if pir.motion_detected:
                lights.stop()
                return True
            if time.time() - start >= 60:
                lights.stop()
                return False
            time.sleep(0.2)

    except Exception:
        # print("[MOTION ERROR]", e)
        pass
    return False
