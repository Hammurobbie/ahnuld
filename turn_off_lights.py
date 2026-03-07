import os
import sys
import json
import asyncio
import requests

from pywizlight import wizlight

async def main():
    wiz_ips = [ip.strip() for ip in os.environ.get("WIZ_BULB_IPS", "").split(",") if ip.strip()]
    bulbs = [wizlight(ip) for ip in wiz_ips]

    hue_base = f"http://{os.environ.get('HUE_BRIDGE_IP', '')}/api/{os.environ.get('HUE_API_KEY', '')}"
    urlG = f'{hue_base}/lights/'
    responseG = requests.get(urlG)
    lights = json.loads(responseG.text)

    for light in lights:
        url = f'{urlG}{light}/state'
        payload = json.dumps({"on": False})
        requests.put(url, payload)

    await asyncio.gather(*(bulb.turn_off() for bulb in bulbs))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(main())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(main())
