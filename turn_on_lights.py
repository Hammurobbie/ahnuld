import asyncio
import os
import sys
import requests
import json
import time

from play_audio import play_audio
from pywizlight import wizlight, PilotBuilder
from capture_environmental_colors import capture_environmental_colors

_HUE_BASE = f"http://{os.environ.get('HUE_BRIDGE_IP', '')}/api/{os.environ.get('HUE_API_KEY', '')}"

async def main():
    codes = sys.argv
    if len(codes) < 2:
        codes.append("")

    hueLights = None
    ledLights = None

    wiz_ips = [ip.strip() for ip in os.environ.get("WIZ_BULB_IPS", "").split(",") if ip.strip()]
    bulbs = [wizlight(ip) for ip in wiz_ips]

    theme = codes[1]
    if len(codes) > 2 and codes[2]:
        ledLights = codes[2]

    is_video_mode = theme in ["videomode"]

    if not is_video_mode:
        ledLights.set_color("thinking")

    def success_lights():
        ledLights.set_color("success")
        ledLights.change_after(6, "idle")
        time.sleep(2)

    def error_lights():
        ledLights.set_color("error")
        play_audio("idk")
        ledLights.change_after(6, "idle")
        time.sleep(2)

    if theme in ["sleep"]:
        hue_ids = [2, 4, 8, 10]
        url_base = f"{_HUE_BASE}/lights"

        for hue_id in hue_ids:
            url = f"{url_base}/{hue_id}/state"
            payload = json.dumps({"on": False})
            requests.put(url, payload)
        success_lights()
        return

    elif theme in ["read"]:
        hue_ids = [2, 4, 8, 10]
        url_base = f"{_HUE_BASE}/lights"

        for hue_id in hue_ids:
            url = f"{url_base}/{hue_id}/state"
            payload = json.dumps({
                "on": True,
                "bri": 120,
                "xy": [0.57, 0.412]
            })
            requests.put(url, payload)

        for hue_id in [8, 10]:
            url = f"{url_base}/{hue_id}/state"
            payload = json.dumps({"on": False})
            requests.put(url, payload)
        success_lights()
        return

    elif theme in ["cinema"]:
        theater_hue_ids = [5, 6, 7, 13, 14]
        hue_ids = [2, 4, 3, 8, 10, 9, 11, 12]
        url_base = f"{_HUE_BASE}/lights"

        url = f"{url_base}/1/state"
        payload = json.dumps({"on": False})
        requests.put(url, payload)

        for hue_id in theater_hue_ids:
            url = f"{url_base}/{hue_id}/state"
            payload = json.dumps({
                "on": True,
                "bri": 25,
            })
            requests.put(url, payload)

        for hue_id in hue_ids:
            url = f"{url_base}/{hue_id}/state"
            payload = json.dumps({
                "on": True,
                "bri": 75,
            })
            requests.put(url, payload)

        success_lights()

    elif theme in ["midnightinparis"]:
        r, g, b, br = 200, 50, 0, 125

    elif theme in ["moonrisekingdom"]:
        r, g, b, br = 200, 50, 0, 254

    elif theme in ["speakeasy"]:
        r, g, b, br = 245, 112, 0, 223

    elif theme in ["shmash"]:
        hueLights = list(range(1, 15))
        r, g, b, r2, g2, b2, br = 220, 50, 0, 220, 50, 0, 100

    elif theme in ["cherryblossom"]:
        hueLights = [7, 1, 2, 4, 3, 5, 6, 8, 10, 9, 11, 12, 13, 14]
        r, g, b, r2, g2, b2, br = 200, 80, 40, 250, 50, 50, 175

    elif theme in ["cyberpunk"]:
        hueLights = [7, 1, 2, 4, 3, 5, 6, 8, 10, 9, 11, 12, 13, 14]
        r, g, b, r2, g2, b2, br = 250, 0, 80, 0, 220, 252, 254

    elif theme in ["bladerunner"]:
        hueLights = [7, 1, 2, 4, 3, 5, 6, 8, 10, 9, 11, 12, 13, 14]
        r, g, b, r2, g2, b2, br = 255, 60, 0, 0, 200, 250, 254

    elif theme in ["alien"]:
        hueLights = [7, 1, 2, 4, 3, 5, 6, 8, 10, 9, 11, 12, 13, 14]
        r, g, b, r2, g2, b2, br = 0, 128, 0, 255, 255, 1, 254

    elif theme in ["godfather"]:
        hueLights = [7, 1, 2, 4, 3, 5, 6, 8, 10, 9, 11, 12, 13, 14]
        r, g, b, r2, g2, b2, br = 250, 0, 0, 255, 55, 1, 120

    elif theme in ["brucealmighty"]:
        hueLights = list(range(1, 15))
        r, g, b, r2, g2, b2, br = 250, 250, 250, 250, 250, 250, 255

    elif theme in ["titanic"]:
        hueLights = list(range(1, 15))
        r, g, b, r2, g2, b2, br = 0, 0, 250, 0, 50, 250, 120

    elif theme in ["prestige"]:
        hueLights = list(range(1, 15))
        r, g, b, br = 200, 80, 20, 255

    elif theme in ["videomode"]:
        ledLights.stop()
        hueLights = [7, 1, 2, 4, 3, 5, 6, 8, 10, 9, 11, 12, 13, 14]
        colors = capture_environmental_colors()

        if colors and len(colors) >= 2:
            r, g, b = colors[0][0], colors[0][1], colors[0][2]
            r2, g2, b2 = colors[1][0], colors[1][1], colors[1][2]
            br = 75
        else:
            error_lights()
            return

    elif theme in ["fairfax"]:
        payload = {"on": True, "scene": "K0mIvJNac9-6CnL"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )

    elif theme in ["snowday"]:
        payload = {"on": True, "scene": "MZejKTLSy-cZsn4f"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )

    elif theme in ["moonlight"]:
        payload = {"on": True, "scene": "1ofOoEOk2gavw0BN"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )

    elif theme in ["ibiza"]:
        payload = {"on": True, "scene": "FRYZyq4vHCy6fNqg"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )

    elif theme in ["osaka"]:
        payload = {"on": True, "scene": "1advVnvQsMVBKcJd"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )

    elif theme in ["dreamydusk"]:
        payload = {"on": True, "scene": "k1AQMyRm1jmxpQaZ"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )

    elif theme in ["singapore"]:
        payload = {"on": True, "scene": "nmUphMMPpDa3220I"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )

    elif theme in ["galaxy"]:
        payload = {"on": True, "scene": "6btFza2Zi46dH09"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )
    elif theme in ["tokyo"]:
        payload = {"on": True, "scene": "C6zGdPF-UtFxn6N"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )
    elif theme in ["lavalamp"]:
        payload = {"on": True, "scene": "WbJ9oaRrFRnbuBDt"}
        requests.put(
            f"{_HUE_BASE}/groups/4/action",
            json.dumps(payload)
        )
    else:
        error_lights()
        return


    if hueLights and theme != "prestige":
        X = r * 0.649926 + g * 0.103455 + b * 0.197109
        Y = r * 0.234327 + g * 0.743075 + b * 0.022598
        Z = r * 0.0 + g * 0.053077 + b * 1.035763

        x = round(X / (X + Y + Z), 4)
        y = round(Y / (X + Y + Z), 4)
        pyPay = {"on": True, "bri": br, "xy": [x, y]}

        if "r2" in locals():
            X2 = r2 * 0.649926 + g2 * 0.103455 + b2 * 0.197109
            Y2 = r2 * 0.234327 + g2 * 0.743075 + b2 * 0.022598
            Z2 = r2 * 0.0 + g2 * 0.053077 + b2 * 1.035763

            x2 = round(X2 / (X2 + Y2 + Z2), 4)
            y2 = round(Y2 / (X2 + Y2 + Z2), 4)
            pyPay2 = {"on": True, "bri": br, "xy": [x2, y2]}
        else:
            pyPay2 = pyPay

        switcher = False
        for hueLight in hueLights:
            url = f"{_HUE_BASE}/lights/{hueLight}/state"
            payload = json.dumps(pyPay2 if switcher else pyPay)

            theater_hue_ids = [5, 6, 7, 13, 14]

            if is_video_mode:
                payload_dict = pyPay2.copy() if switcher else pyPay.copy()

                if hueLight == 1:
                    payload_dict = {"on": False}
                elif hueLight in theater_hue_ids:
                    payload_dict["bri"] = 25

                payload = json.dumps(payload_dict)

            requests.put(url, payload)
            switcher = not switcher
            time.sleep(0.25)

        if theme in ["bladerunner", "cyberpunk"]:
            g2, b2 = 250, 120

    elif theme not in ["snowday", "lavalamp", "fairfax", "galaxy", "moonlight", "ibiza", "dreamydusk", "osaka", "singapore", "tokyo", "cinema"]:
        responseG = requests.get(
f"{_HUE_BASE}/lights/"
        )
        lights = json.loads(responseG.text)

        X = r * 0.649926 + g * 0.103455 + b * 0.197109
        Y = r * 0.234327 + g * 0.743075 + b * 0.022598
        Z = r * 0.0 + g * 0.053077 + b * 1.035763

        x = round(X / (X + Y + Z), 4)
        y = round(Y / (X + Y + Z), 4)

        pyPay = {"on": True, "bri": br, "xy": [x, y]}
        for light in lights:
            url = f"{_HUE_BASE}/lights/{light}/state"
            requests.put(url, json.dumps(pyPay))

    else:
        r, g, b, br = 245, 112, 0, 223

    try:
        pb = PilotBuilder(rgb=(r, g, b), brightness=br)

        if theme in ["cinema", "videomode"]:
            br = 20
            pb = PilotBuilder(brightness=br)

        await asyncio.gather(
            bulbs[0].turn_on(pb),
            bulbs[1].turn_on(pb),
            bulbs[2].turn_on(pb),
            bulbs[3].turn_on(pb),
        )
    except Exception as e:
        # print(f"An error occurred: {e}")
        pass
    finally:
        success_lights()

if __name__ == "__main__":
    asyncio.run(main())
