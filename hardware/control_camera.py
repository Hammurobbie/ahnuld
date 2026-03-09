import gc
import time
import random
from hardware.camera import Camera
from audio import play_audio
from face import compare_faces
from face import recognize_face
from lights import get_current_states, activate_scene, restore_states

def access_denied(lights):
    lights.set_color("error")
    lights.change_after(6)

def control_camera(lights):
    try:
        prev_states = get_current_states()
        activate_scene("bright")
        cam = Camera()
        recognizer = recognize_face()
        scan_attempts = 0
        timer = 0
        while True:
            timer += 1
            frame = cam.capture_frame()
            embeddings = recognizer.extract_embedding(frame)

            if timer > 30:
                access_denied(lights)
                play_audio(random.choice(["who_are_you", "dont_bullshit_me", "get_out"]))
                return True

            if embeddings:
                matches = compare_faces(embeddings)

                if scan_attempts >= 20:
                    access_denied(lights)
                    play_audio(random.choice(["who_are_you", "dont_bullshit_me", "get_out"]))
                    return True

                elif not matches:
                    scan_attempts += 1
                else:
                    lights.set_color("success")
                    lights.change_after(6)
                    is_robbie = "robbie" in matches
                    is_ali = "ali" in matches
                    if is_robbie and is_ali:
                        play_audio("missed_u_guys")
                    elif is_robbie:
                        play_audio("robbie_sonuva_bitch")
                    elif is_ali:
                        play_audio("look_what_we_have_here")
                    break

            # cam.show(frame)
            if cam.should_quit():
                break

    finally:
        restore_states(prev_states)
        cam.close()
        Camera.shutdown()
        del recognizer
        gc.collect()
        time.sleep(1)
