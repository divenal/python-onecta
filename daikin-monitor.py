#!/usr/bin/env python3

"""A simple script to print some sensor temperatures every 10 minutes."""

from datetime import datetime
import time
import logging
import gzip

from daikin import Daikin

_logger = logging.getLogger(__name__)


def setup_logging(zf):
    # log to both zf and console

    gz_log_handler = logging.StreamHandler(zf)
    _logger.addHandler(gz_log_handler)

    stderr_log_handler = logging.StreamHandler()
    _logger.addHandler(stderr_log_handler)

    # prefix timestamp onto the file logger
    formatter = logging.Formatter(
        fmt="%(asctime)s: %(message)s", datefmt="%Y-%m-%d--%H:%M"
    )
    gz_log_handler.setFormatter(formatter)

    _logger.setLevel(logging.DEBUG)


def monitor():
    daikin = Daikin()

    while True:
        mp = daikin.management_points()

        mz = mp["climateControlMainZone"]["sensoryData"]["value"]
        lwt = mz["leavingWaterTemperature"]["value"]
        outdoor = mz["outdoorTemperature"]["value"]
        room = mz["roomTemperature"]["value"]

        tc = mp["climateControlMainZone"]["temperatureControl"]["value"]
        # should this be "auto", or "heating" ?
        target = tc["operationModes"]["auto"]["setpoints"]["roomTemperature"]["value"]
        offs = tc["operationModes"]["auto"]["setpoints"]["leavingWaterOffset"]["value"]

        hwt = mp["domesticHotWaterTank"]["sensoryData"]["value"]
        hw = hwt["tankTemperature"]["value"]

        # now = datetime.now()
        _logger.info(
            "outdoor=%2d room=%2.1f / %2.1f hw=%d  lwt=%d (offs=%d)",
            outdoor,
            room,
            target,
            hw,
            lwt,
            offs,
        )

        # API requests are limited to 200 per day
        # They suggest one per 10 minutes, which leaves around 50 for
        # actually controlling the system. Or perhaps downloading
        # consumption figures at the end of the day.
        time.sleep(600)


def main():
    now = datetime.now()
    tstamp = now.strftime("%Y%m%d-%H%M")

    with gzip.open(filename="/tmp/daikin." + tstamp + ".log.gz", mode="wt") as zf:
        setup_logging(zf)
        monitor()


if __name__ == "__main__":
    main()
