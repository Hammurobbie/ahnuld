from __future__ import annotations

import os
import time
import random
import logging
import traceback
import warnings

from dotenv import load_dotenv
load_dotenv()

# Disable all logging from native libs so daemon doesn't accumulate log output / memory
os.environ["VOSK_LOG_LEVEL"] = "-1"
os.environ["ORT_LOG_LEVEL"] = "4"   # 4 = fatal only (suppress all else)
os.environ["LIBCAMERA_LOG_LEVELS"] = "*:4"  # 4 = fatal only (libcamera minimum)
os.environ["INSIGHTFACE_LOG_LEVEL"] = "0"

# Disable Python loggers for these libs: no output, no propagation, no buffer growth
def _silence_logger(name: str) -> None:
    log = logging.getLogger(name)
    log.setLevel(logging.CRITICAL + 1)  # nothing passes
    log.addHandler(logging.NullHandler())
    log.propagate = False


for _name in ("insightface", "onnxruntime", "picamera2", "libcamera"):
    _silence_logger(_name)

warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=UserWarning, module='gpiozero.output_devices')

from audio import play_audio
from hardware import detect_motion, control_servo, control_camera
from lights import LightController
from commands.actions import self_destruct
from commands.engine import handle_commands


logger = logging.getLogger("ahnuld")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> None:
    auth_attempts = 0
    lights = LightController()
    lights.set_color("success")
    lights.change_after(6)
    time.sleep(1)
    play_audio(random.choice(["hello", "ahnuld"]))
    while True:
        is_motion_detected = detect_motion(lights)
        if not is_motion_detected:
            break
        control_servo()
        play_audio("who_is_it")
        time.sleep(1)
        is_unauthorized = control_camera(lights)
        control_servo(True)
        if is_unauthorized and auth_attempts < 4:
            auth_attempts += 1
            break
        elif is_unauthorized:
            self_destruct(lights)
        handle_commands(lights)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.critical("Unhandled crash:\n%s", traceback.format_exc())
        raise
