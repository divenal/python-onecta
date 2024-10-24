#!/usr/bin/env python3

"""A simple script to print some sensor temperatures every 10 minutes."""

from datetime import datetime
import time

from daikin import Daikin

def main():
    daikin = Daikin()

    while True:
        gw = daikin.get("gateway-devices")

        # could write the raw data to a file in /tmp

        # build a dictionary of the management points,
        # keyed on the embeddedId, so that we can look them up
        # by name rather than searching in the array for them
        mp = {item["embeddedId"]: item for item in gw[0]["managementPoints"]}

        mz = mp["climateControlMainZone"]["sensoryData"]["value"]
        lwt = mz["leavingWaterTemperature"]["value"]
        outdoor = mz["outdoorTemperature"]["value"]
        room = mz["roomTemperature"]["value"]

        hwt = mp["domesticHotWaterTank"]["sensoryData"]["value"]
        hw = hwt["tankTemperature"]["value"]

        now = datetime.now()
        print(f"{now}: outdoor={outdoor}, room={room}, hw={hw}, lwt={lwt}")

        # API requests are limited to 200 per day
        # They suggest one per 10 minutes, which leaves around 50 for
        # actually controlling the system. Or perhaps downloading
        # consumption figures at the end of the day.
        time.sleep(600)
    

if __name__ == "__main__":
    main()
