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
    formatter = logging.Formatter(fmt="%(asctime)s: %(message)s", datefmt="%Y-%m-%d--%H-%M")
    gz_log_handler.setFormatter(formatter)

    _logger.setLevel(logging.DEBUG)

    # and off we go...

    daikin = Daikin()
    myenergi = MyenergiApi()

    while True:

        # heatpump is attached to CT#2
        # direction is backwards so that app animates it correctly
        stat = myenergi.get('/cgi-jstatus-Z')
        zappi = stat['zappi'][0]
        power = -zappi['ectp3']


        gw = daikin.get("gateway-devices")

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

        # now = datetime.now()
        _logger.info("power=%4d outdoor=%2d room=%2.1f hw=%d lwt=%d", power, outdoor, room, hw, lwt)

        # Daikin API requests are limited to 200 per day
        # They suggest one per 10 minutes, which leaves around 50 for
        # actually controlling the system. Or perhaps downloading
        # consumption figures at the end of the day.
        time.sleep(600)
    
if __name__ == "__main__":
    main()
