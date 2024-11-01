#!/usr/bin/env python3

"""A simple script to print some sensor temperatures every 10 minutes."""

from datetime import datetime
import time
import logging
import gzip

from daikin import Daikin

_logger = logging.getLogger(__name__)

def main():

    # log to both file and console

    now = datetime.now()
    tstamp = now.strftime("%Y%m%d-%H%M")

    zf = gzip.open(filename="/tmp/daikin." + tstamp + ".log.gz", mode="wt")
    gz_log_handler = logging.StreamHandler(zf)
    _logger.addHandler(gz_log_handler)

    stderr_log_handler = logging.StreamHandler()
    _logger.addHandler(stderr_log_handler)

    # prefix timestamp onto the file logger
    formatter = logging.Formatter(fmt="%(asctime)s: %(message)s", datefmt="%Y-%m-%d--%H:%M")
    gz_log_handler.setFormatter(formatter)

    _logger.setLevel(logging.DEBUG)

    # and off we go...

    daikin = Daikin()

    while True:
        mp = daikin.management_points()

        mz = mp["climateControlMainZone"]["sensoryData"]["value"]
        lwt = mz["leavingWaterTemperature"]["value"]
        outdoor = mz["outdoorTemperature"]["value"]
        room = mz["roomTemperature"]["value"]

        hwt = mp["domesticHotWaterTank"]["sensoryData"]["value"]
        hw = hwt["tankTemperature"]["value"]

        # now = datetime.now()
        _logger.info("outdoor=%2d room=%2.1f hw=%d lwt=%d", outdoor, room, hw, lwt)

        # API requests are limited to 200 per day
        # They suggest one per 10 minutes, which leaves around 50 for
        # actually controlling the system. Or perhaps downloading
        # consumption figures at the end of the day.
        time.sleep(600)
    

if __name__ == "__main__":
    main()
