from __future__ import annotations

from typing import Any

import gpiozero
from time import sleep


class ServoController:
    servo: Any = None

    @classmethod
    def get_servo(cls) -> Any:
        if cls.servo is None:
            maxW = 2.5 / 1000
            minW = 0.7 / 1000
            cls.servo = gpiozero.Servo(18, min_pulse_width=minW, max_pulse_width=maxW)
            cls.servo.value = 1
        return cls.servo

    @classmethod
    def shutdown(cls) -> None:
        if cls.servo:
            cls.servo.close()
            cls.servo = None

def control_servo(close: bool | None = None) -> None:
    try:
        servo = ServoController.get_servo()

        if close:
            servo.value = -1
            sleep(2)
            servo.value = 1
        else:
            servo.value = 1
            sleep(2)
            servo.value = -1
    except Exception:
        pass

    finally:
        ServoController.shutdown()
