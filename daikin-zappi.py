#!/usr/bin/env python3

"""A simple script to print some state every 10 minutes.

The temperatures come from the daikin site.
The power consumption comes from myenergi.
"""

from datetime import datetime
import time
import logging
import gzip

from daikin import Daikin
from myenergi import MyenergiApi

_logger = logging.getLogger(__name__)


def setup_logging(zf):
    # log to both file and console

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
    myenergi = MyenergiApi()

    while True:
        # heatpump is attached to CT#2
        # direction is backwards so that app animates it correctly
        stat = myenergi.get("/cgi-jstatus-Z")
        zappi = stat["zappi"][0]
        power = -zappi["ectp3"]

        mp = daikin.management_points()

        # from time to time this produces empty results
        try:
            sd = mp["climateControlMainZone"]["sensoryData"]["value"]
            lwt = sd["leavingWaterTemperature"]["value"]
            outdoor = sd["outdoorTemperature"]["value"]
            room = sd["roomTemperature"]["value"]

            tc = mp["climateControlMainZone"]["temperatureControl"]["value"]
            # should this be "auto", or "heating" ?
            target = tc["operationModes"]["auto"]["setpoints"]["roomTemperature"]["value"]
            offs = tc["operationModes"]["auto"]["setpoints"]["leavingWaterOffset"]["value"]

            tc = mp["climateControlMainZone"]["temperatureControl"]["value"]
            # should this be "auto", or "heating" ?
            target = tc["operationModes"]["auto"]["setpoints"]["roomTemperature"]["value"]

            hwt = mp["domesticHotWaterTank"]["sensoryData"]["value"]
            hw = hwt["tankTemperature"]["value"]

            _logger.info(
                "power=%4d outdoor=%2d room=%2.1f / %2.1f hw=%d  lwt=%d (offs=%d)",
                power,
                outdoor,
                room,
                target,
                hw,
                lwt,
                offs,
            )
        except KeyError:
            _logger.warning("Hmm - got a key error")

        # Daikin API requests are limited to 200 per day
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
