#!/usr/bin/env python3
"""Run the same two servo sequences as main (no lights/camera). Repo root on sys.path."""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from hardware.control_servo import control_servo


def main() -> None:
    print("1) Open 2s → close 2s  (control_servo())")
    control_servo()
    print("2) Close 2s → open 2s  (control_servo(close=True))")
    control_servo(True)
    print("Done.")


if __name__ == "__main__":
    main()
