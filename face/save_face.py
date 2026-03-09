import os
import cv2
import time
import json

from hardware.camera import Camera
from hardware.control_servo import control_servo
from face.recognize_face import recognize_face
from lights import get_current_states, activate_scene, restore_states


def save_face(face, idx, img):
    base_dir = os.path.dirname(__file__)
    save_dir = os.path.join(base_dir, "faces")
    os.makedirs(save_dir, exist_ok=True)

    box = face.bbox.astype(int)
    x1, y1, x2, y2 = box
    cropped_face = img[y1:y2, x1:x2]

    base_name = f"face_{idx + x1}"
    img_path = os.path.join(save_dir, f"{base_name}.jpg")
    json_path = os.path.join(save_dir, f"{base_name}.json")

    cv2.imwrite(img_path, cv2.cvtColor(cropped_face, cv2.COLOR_RGB2BGR))

    with open(json_path, "w") as f:
        json.dump(face.embedding.tolist(), f)


def capture_new_faces():
    prev_states = get_current_states()
    activate_scene("bright")
    cam = Camera()
    recognizer = recognize_face()
    idx = 0
    control_servo()
    print("Capturing faces. Press Ctrl+C to stop.")

    try:
        while True:
            frame = cam.capture_frame()
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = recognizer.app.get(img)

            if faces:
                for face in faces:
                    save_face(face, idx, img)
                    print(f"Saved face {idx}")
                    idx += 1

    except KeyboardInterrupt:
        print("Stopped capturing.")

    finally:
        restore_states(prev_states)
        cam.close()
        Camera.shutdown()
        control_servo(True)


if __name__ == "__main__":
    capture_new_faces()
