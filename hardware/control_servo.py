from __future__ import annotations

from typing import Any

import gpiozero
from time import sleep

# min/max pulse set open/close travel; value -1 hits MIN (full close). If the door hits a hard stop,
# the servo will buzz while held there — fine for short holds (seconds), bad if left stalled for minutes
# (heat, gear wear, extra current). Detach (value=None) after close if you ever need long idle closed.
SERVO_MIN_PULSE = 0.6 / 1000
SERVO_MAX_PULSE = 2.3 / 1000


class ServoController:
    servo: Any = None

    @classmethod
    def get_servo(cls) -> Any:
        if cls.servo is None:
            cls.servo = gpiozero.Servo(
                18,
                min_pulse_width=SERVO_MIN_PULSE,
                max_pulse_width=SERVO_MAX_PULSE,
            )
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
