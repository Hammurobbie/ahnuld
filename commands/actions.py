import os, sys, time, random, asyncio
from thefuzz import fuzz
import commands.config as config
from audio import play_audio, text_to_speech
from lights.turn_off_lights import main as kill_lights
from lights import activate_theme

def throw_error(lights, error=None):
    if error:
        text_to_speech(str(error))
    else:
        play_audio("did_i_do_wrong")
    lights.set_color("error")
    lights.change_after(6, "idle")

def flush_queue(q):
    while not q.empty():
        try:
            q.get_nowait()
        except Exception as e:
            break

def greet(lights, extra=None, audio_queue=None):
    if config.AWAKE:
        return
    try:
        options = ["hi", "howdy", "want"]
        play_audio(random.choice(options))
        if audio_queue:
            flush_queue(audio_queue)
        time.sleep(2)
    except Exception as e:
        throw_error(lights, e)

def turn_off_lights(lights, extra=None):
    try:
        lights.set_color("thinking")
        asyncio.run(kill_lights())
        time.sleep(4)
        lights.set_color("success")
        lights.change_after(6, "idle")
    except Exception as e:
        throw_error(lights, e)

def turn_on_lights(lights, theme=None):
    try:
        asyncio.run(activate_theme(theme, led_lights=lights))
    except Exception as e:
        throw_error(lights, e)

def sleep(lights, extra=None):
    try:
        lights.stop()
    except Exception as e:
        throw_error(lights, e)
    config.AWAKE = False

def shut_down(lights, extra=None):
    try:
        play_audio("hasta")
        lights.set_color("error")
        lights.change_after(6)
        sys.exit(0)
    except Exception as e:
        throw_error(lights, e)

def self_destruct(lights, extra=None):
    try:
        options = ["bye", "hasta", "ill_be_back", "scream"]
        play_audio("count_down")
        lights.set_color("error")
        time.sleep(7)
        play_audio(random.choice(options))
        lights.stop()
        time.sleep(4)
        os.system("sudo shutdown now")
    except Exception as e:
        throw_error(lights, e)

def execute_command(command, lights, text):
    if config.BUSY:
        return
    config.BUSY = True
    try:
        func_name = command["func"]
        theme = None

        if command.get("args"):
            theme_candidate = text.split(command["cmd"], 1)[-1].strip()

            best_theme = None
            highest_score = 0
            threshold = 80

            for known in config.KNOWN_THEMES:
                score = fuzz.partial_ratio(theme_candidate, known)
                if score > highest_score and score >= threshold:
                    best_theme = known
                    highest_score = score

            theme = best_theme or theme_candidate.replace(" ", "")

        if func_name in globals():
            globals()[func_name](lights, theme)
        else:
            text_to_speech("I don't know that command.")
    except Exception as e:
        throw_error(lights, e)
    finally:
        config.BUSY = False
