#!/usr/bin/env python3
"""Exercise PIR (BCM 17), servo (BCM 18), NeoPixels (board.D19 / BCM 19). Run on the Pi from repo root."""

from __future__ import annotations

import os
import sys
import time
import traceback

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def test_pir() -> bool:
    print("\n=== PIR (gpiozero MotionSensor, BCM 17) ===")
    try:
        from gpiozero import MotionSensor

        pir = MotionSensor(17)
        ok = True
        for i in range(8):
            m = pir.motion_detected
            print(f"  sample {i + 1}/8: motion_detected={m}")
            time.sleep(0.35)
        pir.close()
        print("  PASS: GPIO 17 readable (wave hand near PIR to see motion_detected flip).")
        return ok
    except Exception:
        print("  FAIL:")
        traceback.print_exc()
        return False


def test_neopixels() -> bool:
    print("\n=== NeoPixels (board.D19, 5 pixels, BGR) ===")
    try:
        import board
        from lights.control_lights import Pi5Pixelbuf

        pin = board.D19
        n = 5
        pixels = Pi5Pixelbuf(pin, n, auto_write=False, byteorder="BGR")
        # BGR tuples from LightController
        red_bgr = (0, 0, 255)
        green_bgr = (0, 255, 0)
        off = (0, 0, 0)

        pixels.fill(red_bgr)
        pixels.show()
        print("  Solid RED (BGR) — 2s (look at the strip)")
        time.sleep(2)

        pixels.fill(green_bgr)
        pixels.show()
        print("  Solid GREEN (BGR) — 2s")
        time.sleep(2)

        pixels.fill(off)
        pixels.show()
        print("  OFF")
        print("  PASS: init + show completed without exception.")
        return True
    except Exception:
        print("  FAIL:")
        traceback.print_exc()
        return False


def test_servo() -> bool:
    print("\n=== Servo (gpiozero Servo, BCM 18) ===")
    servo = None
    try:
        import gpiozero

        from hardware.control_servo import SERVO_MAX_PULSE, SERVO_MIN_PULSE

        servo = gpiozero.Servo(
            18, min_pulse_width=SERVO_MIN_PULSE, max_pulse_width=SERVO_MAX_PULSE
        )
        print("  value = 1 (open) — 1.5s")
        servo.value = 1
        time.sleep(1.5)
        print("  value = -1 (full close, may buzz at stop) — 1.5s")
        servo.value = -1
        time.sleep(1.5)
        print("  value = 0 (mid) — 1s")
        servo.value = 0
        time.sleep(1.0)
        print("  value = 1")
        servo.value = 1
        print("  PASS: PWM commands sent (watch horn movement).")
        return True
    except Exception:
        print("  FAIL:")
        traceback.print_exc()
        return False
    finally:
        if servo is not None:
            try:
                servo.close()
            except Exception:
                pass


def main() -> int:
    print("Hardware diagnostic (ahnuld): BCM 17=PIR, BCM 18=servo, BCM 19=D19 NeoPixel data")
    results: list[tuple[str, bool]] = []

    results.append(("NeoPixels", test_neopixels()))
    results.append(("Servo", test_servo()))
    results.append(("PIR", test_pir()))

    print("\n=== Summary ===")
    for name, ok in results:
        print(f"  {name}: {'OK' if ok else 'FAILED'}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
