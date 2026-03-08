import os
import time
import random
import logging
import warnings

from dotenv import load_dotenv
load_dotenv()

os.environ["VOSK_LOG_LEVEL"] = "0"
os.environ["ORT_LOG_LEVEL"] = "0"
os.environ["LIBCAMERA_LOG_LEVEL"] = "0"
os.environ["INSIGHTFACE_LOG_LEVEL"] = "0"

logging.getLogger("insightface").setLevel(logging.ERROR)

warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=UserWarning, module='gpiozero.output_devices')

from play_audio import play_audio
from detect_motion import detect_motion
from control_servo import control_servo
from control_camera import control_camera
from control_lights import LightController
from commands.actions import self_destruct
from commands.engine import handle_commands


def main():
    auth_attempts = 0
    lights = LightController()
    lights.set_color("success")
    lights.change_after(6)
    time.sleep(1)
    play_audio(random.choice(["hello", "ahnuld"]))
    while True:
        handle_commands(lights)
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
    main()
