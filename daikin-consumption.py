#!/usr/bin/env python3

"""A simple script to display consumption data.

Parameter d for day, w for week, m for months.
('m' is a bit anomalous - 'd' shows hours over 2 days;
 'w' shows days over two weeks, but 'm' shows months
 over two years - should really have been 'y')

The assumption is that you want the previous interval, since that
is complete. ie for 'd' you get yesterday, w you get last week, m you
get last year.

I anticipate that you might run this say 4am every day to get yesterday's
results, or on monday morning to get last week's results, once they're complete.
"""

import datetime
import sys

from daikin import Daikin


def main():
    if len(sys.argv) == 1 or sys.argv[1] not in ("d", "w", "m"):
        print(f"Usage: {sys.argv[0]} [d|w|m]")
        return
    want = sys.argv[1]

    daikin = Daikin()

    mp = daikin.management_points()

    today = datetime.datetime.now().date()
    if want == "d":
        delta = datetime.timedelta(days=1)  # wind back one day to yesterday
        start = today - delta
        count = 12
    elif want == "w":
        # wind back 7 days plus whichever day number this is (mon=0, tue=1, ...)
        # The results start on a Monday
        delta = datetime.timedelta(days=today.weekday() + 7)
        start = today - delta
        count = 7
    else:
        # start date is 1st Jan in the previous year
        start = datetime.date(year=today.year - 1, month=1, day=1)
        count = 12

    for device in ("climateControlMainZone", "domesticHotWaterTank"):
        consumption = mp[device]["consumptionData"]["value"]["electrical"]["heating"][
            want
        ]
        print(f"{start} {device:22s} ", *(f"{x:3d}" for x in consumption[0:count]))


if __name__ == "__main__":
    main()
