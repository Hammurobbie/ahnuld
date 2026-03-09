from __future__ import annotations

import colorsys
import time

import cv2
import numpy as np
from hardware.camera import Camera
from hardware.control_servo import control_servo
from lights import get_current_states, restore_states, turn_off


def capture_environmental_colors() -> list[list[int]]:
    prev_states = get_current_states()
    turn_off()

    cam = Camera()
    control_servo()

    try:
        frame = cam.capture_frame()
        img = frame[:, :, :3]

        # adjust white balance
        img = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
        avg_a = np.mean(img[:, :, 1])
        avg_b = np.mean(img[:, :, 2])
        img[:, :, 1] = img[:, :, 1] - ((avg_a - 128) * 0.5)
        img[:, :, 2] = img[:, :, 2] - ((avg_b - 128) * 0.5)
        img = cv2.cvtColor(img, cv2.COLOR_LAB2RGB)

        # crop image in half
        height, width = img.shape[:2]
        img = img[:, width//2:]

        # cv2.imwrite("img.jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

        pixels = img.reshape(-1, 3)
        pixels = pixels[::10]

        brightness = np.mean(pixels, axis=1)
        bright_pixels = pixels[brightness > 80]

        # filter out unsaturated colors
        max_vals = np.max(bright_pixels, axis=1)
        min_vals = np.min(bright_pixels, axis=1)
        saturation = (max_vals - min_vals) / (max_vals + 1e-6)

        # First try to find highly saturated colors
        saturated_pixels = bright_pixels[saturation > 0.7]

        if len(saturated_pixels) > 0:
            # We have saturated colors - use them
            rounded = saturated_pixels / 10
            rounded = np.round(rounded) * 10
            unique, counts = np.unique(rounded, axis=0, return_counts=True)

            # Score each color by saturation and presence
            scores = []
            for i, color in enumerate(unique):
                r, g, b = color
                max_c = max(r, g, b)
                min_c = min(r, g, b)
                color_sat = (max_c - min_c) / (max_c + 1e-6)
                score = color_sat * np.sqrt(counts[i])
                scores.append(score)

            pop_idx = np.argmax(scores)
            pop_color = unique[pop_idx].astype(int).tolist()

            # Light boost for already saturated colors
            r, g, b = pop_color
            boost = 1.3
            avg = (r + g + b) / 3
            r = int(np.clip(avg + (r - avg) * boost, 0, 255))
            g = int(np.clip(avg + (g - avg) * boost, 0, 255))
            b = int(np.clip(avg + (b - avg) * boost, 0, 255))
            pop_color = [r, g, b]

        else:
            # No saturated colors - fall back to less saturated and boost heavily
            less_saturated = bright_pixels[saturation > 0.3]

            if len(less_saturated) == 0:
                restore_states(prev_states)
                return []

            rounded = less_saturated / 10
            rounded = np.round(rounded) * 10
            unique, counts = np.unique(rounded, axis=0, return_counts=True)

            # Score and pick best unsaturated color
            scores = []
            for i, color in enumerate(unique):
                r, g, b = color
                max_c = max(r, g, b)
                min_c = min(r, g, b)
                color_sat = (max_c - min_c) / (max_c + 1e-6)
                score = color_sat * np.sqrt(counts[i])
                scores.append(score)

            pop_idx = np.argmax(scores)
            pop_color = unique[pop_idx].astype(int).tolist()

            # Heavy boost for unsaturated colors
            r, g, b = pop_color
            boost = 8.0
            avg = (r + g + b) / 3
            r = int(np.clip(avg + (r - avg) * boost, 0, 255))
            g = int(np.clip(avg + (g - avg) * boost, 0, 255))
            b = int(np.clip(avg + (b - avg) * boost, 0, 255))
            pop_color = [r, g, b]

        # find complementary color
        r, g, b = pop_color
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)

        comp_h = (h + 0.5) % 1.0
        comp_r, comp_g, comp_b = colorsys.hsv_to_rgb(comp_h, s, v)

        comp_color = [int(comp_r * 255), int(comp_g * 255), int(comp_b * 255)]
        colors = [pop_color, comp_color]

        return colors

    finally:
        cam.close()
        Camera.shutdown()
        control_servo(True)

if __name__ == "__main__":
    capture_environmental_colors()
