from __future__ import annotations

import os
import asyncio

from pywizlight import wizlight
from lights.hue_api import turn_off_all


async def main() -> None:
    turn_off_all()

    wiz_ips = [ip.strip() for ip in os.environ.get("WIZ_BULB_IPS", "").split(",") if ip.strip()]
    bulbs = [wizlight(ip) for ip in wiz_ips]
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
