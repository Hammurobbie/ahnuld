import time
import threading
import adafruit_pixelbuf
import board
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_raspberry_pi5_neopixel_write import neopixel_write

class Pi5Pixelbuf(adafruit_pixelbuf.PixelBuf):
    def __init__(self, pin, size, **kwargs):
        try:
            self._pin = pin
            super().__init__(size=size, **kwargs)
        except Exception:
            # print("[PIXELBUF INIT ERROR]", e)
            pass

    def _transmit(self, buf):
        try:
            neopixel_write(self._pin, buf)
        except Exception:
            # print("[TRANSMIT ERROR]", e)
            pass

class LightController:
    def __init__(self):
        try:
            self.NEOPIXEL = board.D19
            self.num_pixels = 5

            self.BLUE = (200, 30, 0)
            self.CYAN = (30, 0, 150)
            self.PINK = (5, 250, 2)
            self.ORANGE = (0, 250, 50)
            self.DIM_WHITE = (25, 24, 20)

            self.pixels = Pi5Pixelbuf(
                self.NEOPIXEL, self.num_pixels, auto_write=False, byteorder="BGR"
            )

            self.current_color = None
            self.stop_event = threading.Event()
            self.thread = None
        except Exception:
            # print("[LIGHTCONTROLLER INIT ERROR]", e)
            pass

    def _pulse_loop(self):
        try:
            pulse = Pulse(
                self.pixels,
                color=self.current_color,
                speed=0.005,
                max_intensity=0.75,
                breath=0.5,
            )
            while not self.stop_event.is_set():
                try:
                    pulse.animate()
                    if pulse.color != self.current_color:
                        pulse = Pulse(
                            self.pixels,
                            color=self.current_color,
                            speed=0.005,
                            max_intensity=0.75,
                            breath=0.5,
                        )
                    time.sleep(0.02)
                except Exception:
                    # print("[PULSE LOOP ERROR]", e)
                    pass
        except Exception:
            # print("[PULSE LOOP INIT ERROR]", e)
            pass

    def set_color(self, color_name):
        try:
            if color_name == "idle":
                self.current_color = self.ORANGE
            elif color_name == "success":
                self.current_color = self.CYAN
            elif color_name == "error":
                self.current_color = self.PINK
            elif color_name == "thinking":
                self.current_color = self.BLUE
            elif color_name == "bright":
                self.current_color = self.DIM_WHITE

            if self.thread is None or not self.thread.is_alive():
                self.stop_event.clear()
                self.thread = threading.Thread(target=self._pulse_loop)
                self.thread.start()
        except Exception:
            # print("[SET COLOR ERROR]", e)
            pass

    def set_solid(self, color_name):
        try:
            if self.thread is not None and self.thread.is_alive():
                self.stop_event.set()
                self.thread.join()

            if color_name == "idle":
                color = self.ORANGE
            elif color_name == "success":
                color = self.CYAN
            elif color_name == "error":
                color = self.PINK
            elif color_name == "thinking":
                color = self.BLUE
            elif color_name == "bright":
                color = self.DIM_WHITE
            else:
                color = self.DIM_WHITE

            self.pixels.fill(color)
            self.pixels.show()
        except Exception:
            pass

    def turn_off(self):
        try:
            if self.thread is not None and self.thread.is_alive():
                self.stop_event.set()
                self.thread.join()

            self.pixels.fill((0, 0, 0))
            self.pixels.show()
        except Exception:
            pass

    def stop(self, fade_time=1.0, steps=20):
        try:
            self.stop_event.set()
            self.thread.join()

            current_colors = [self.pixels[i] for i in range(len(self.pixels))]
            for step in range(steps, 0, -1):
                factor = step / steps
                for i, (r, g, b) in enumerate(current_colors):
                    self.pixels[i] = (int(r * factor), int(g * factor), int(b * factor))
                self.pixels.show()
                time.sleep(fade_time / steps)

            self.pixels.fill((0, 0, 0))
            self.pixels.show()
        except Exception:
            # print("[STOP ERROR]", e)
            pass


    def change_after(self, seconds: float, mode=None):
        def delayed():
            time.sleep(seconds)
            if mode:
                self.set_color(mode)
            else:
                self.stop()
        try:
            threading.Thread(target=delayed, daemon=True).start()
        except Exception:
            # print("[STOP ERROR]", e)
            pass

    def is_stopped(self):
        try:
            return self.pixels[0] == [0, 0, 0]
        except Exception:
            return True
