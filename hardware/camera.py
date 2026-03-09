import logging

import cv2
from picamera2 import Picamera2

# Disable Picamera2 Python logging (libcamera C++ logs disabled via LIBCAMERA_LOG_LEVELS in main.py)
try:
    Picamera2.set_logging(logging.CRITICAL + 1)  # no messages
except Exception:
    pass


class Camera:
    picam2 = None
    started = False

    def __init__(self):
        if Camera.picam2 is None:
            Camera.picam2 = Picamera2()
            config = Camera.picam2.create_preview_configuration(main={"size": (1280, 720)})
            Camera.picam2.configure(config)
            Camera.picam2.start()
            Camera.started = True
        self.picam2 = Camera.picam2

    def capture_frame(self):
        frame = self.picam2.capture_array()
        return cv2.convertScaleAbs(frame, alpha=1.2, beta=30)

    def show(self, frame):
        cv2.imshow("Camera", frame)

    def should_quit(self):
        return cv2.waitKey(1) & 0xFF == ord('q')

    def close(self):
        cv2.destroyAllWindows()
        Camera.shutdown()

    @classmethod
    def shutdown(cls):
        if cls.picam2:
            if cls.started:
                cls.picam2.stop()
            cls.picam2.close()
            cls.picam2 = None
            cls.started = False
