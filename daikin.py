#!/usr/bin/env python3

"""
A class to manage access to the Daikin Onecta cloud API.
Plus a simple CLI for getting the initial authentication
established, and testing.
"""

import fcntl
import json
import logging
import pathlib
import os
import requests
import time
import sys

from requests.adapters import HTTPAdapter, Retry
from typing import TextIO

_logger = logging.getLogger(__name__)


class Daikin:
    """Daikin Cloud API access.

    This class handles maintaining the authorization token,
    which is a little convoluted. The token is maintained in
    a file so that it persists between sessions - each token
    only lasts an hour, but comes bundled with a refresh token
    which can be used to generate the next one, and so on.
    Getting started from scratch requires interactive authentication
    using a browser - see main()

    Does not do anything about trying to manage the rate-limiting
    that the API enforces.
    """

    # configuration

    # This points to a trivial generic script running on a free hosting site.
    # It simply echos the 'code' parameter to the page, from which
    # you can paste it in - see the 'code' sub-command in main().
    redir = "https://ibmx20.infinityfreeapp.com/daikin.php"

    # the json-formatted file containing the app details: the "id"
    # and the "secret", and optionally the "device" if you want
    # to make changes.
    app_file = pathlib.Path.home() / ".daikin_app.json"

    # The json file containing the access token - it is the
    # raw data as received from the cloud.
    # This is rewritten every hour, so I don't want it on the pi's sdcard
    # (Losing it isn't particularly serious.)
    key_file = pathlib.Path("/tmp/daikin_key.json")

    # The daikin url prefixes
    # Can use the 'mock' version of the api url while experimenting.
    idp_url = "https://idp.onecta.daikineurope.com/v1/oidc"
    api_url = "https://api.onecta.daikineurope.com/v1"

    app: dict  # the in-memory copy of app_file
    key: dict  # the in-memory copy of key_file

    # times are stored as seconds-since-epoch
    key_modtime: int  # the mod time of key_file when we loaded it
    key_expiry: int  # based on mod time plus "expires_after" (3600 seconds)

    session: requests.Session  # for persisting api connections

    def __init__(self):
        with self.app_file.open() as af:
            self.app = json.load(af)

        self.id = self.app["id"]
        self.secret = self.app["secret"]
        self.device = self.app.get("device", None)

        try:
            with self.key_file.open() as kf:
                # no need to lock the file (and cannot, for read-only)
                self.load_key_file(kf)
        except FileNotFoundError:
            _logger.error(
                "cannot load keys file - you'll need to go through the interactive authentication process"
            )
            self.key = dict()
            self.key_modtime = 0
            self.key_expiry = 0

        session = requests.Session()
        session.headers.update({"Accept-Encoding": "gzip"})
        retries = Retry(total=5, backoff_factor=5)
        session.mount(self.api_url, HTTPAdapter(max_retries=retries))
        self.session = session

    def load_key_file(self, kf: TextIO) -> None:
        """Load the key file, and calculate expiry time.
        Note that the caller must open the file and handle
        locking.
        """

        self.key = json.load(kf)

        # we store the modtime so that we can detect if
        # another process has updated it since we loaded it
        self.key_modtime = os.stat(kf.fileno()).st_mtime
        self.key_expiry = self.key_modtime + self.key["expires_in"] - 30

    def _get_or_refresh_key(self, code=None) -> str:
        """Generate or refresh access token.

        If code is supplied, it is taken as being a new code from
        an interactive authentication. Otherwise we are just using
        the refresh token from an expired key.

        This returns the new key as a json string - it's up to
        the caller to write it to the file. (So they can worry
        about the locking...)
        """

        args = {"client_id": self.id, "client_secret": self.secret}
        if code:
            # it's a new code
            args["grant_type"] = "authorization_code"
            args["code"] = code
            args["redirect_uri"] = self.redir
        else:
            # a refresh
            args["grant_type"] = "refresh_token"
            args["refresh_token"] = self.key["refresh_token"]

        url = self.idp_url + "/token?" + "&".join(f"{a}={b}" for a, b in args.items())
        r = requests.post(url, timeout=30)
        r.raise_for_status()
        return r.text

    def get_new_key(self, code: str) -> None:
        """Wrapper for _get_or_refresh_key() that writes to file"""
        j = self._get_or_refresh_key(code)
        with self.key_file.open(mode="w") as keys:
            # probably no point bothering with lock since this is close to atomic
            # and because it requires interacting with browser, very unlikely
            # that any other client is running at the same time
            print(j, file=keys)
            self.key_modtime = os.fstat(keys.fileno()).st_mtime
        self.key = json.loads(j)
        self.key_expiry = self.key_modtime + self.key["expires_in"] - 30

    def check_key_expiry(self) -> None:
        """Check whether key has expired, and try to update if necessary."""
        now = time.time()
        if now < self.key_expiry:
            # still good.
            return

        with self.key_file.open(mode="r+") as kf:
            fd = kf.fileno()

            # take an exclusive lock.
            # Probably ought to create a "locked_file" thingy so that
            # I can do
            #   with locked_file(name, mode) as kf:
            # then the unlocking would be done automatically. However,
            # the lock is released as soon as the file is closed, so it's
            # not really an issue. (On linux, at least...)
            # I guess I could also do it as a try... finally

            fcntl.flock(fd, fcntl.LOCK_EX)

            modtime = os.fstat(fd).st_mtime
            if modtime > self.key_modtime:
                # seems that another process has already updated the file
                self.load_key_file(kf)

                now = time.time()  # flock() might have blocked for a while
                if now < self.key_expiry:
                    # new key is good
                    fcntl.flock(
                        fd, fcntl.LOCK_UN
                    )  # not really needed - lock vanishes on close
                    return
                # else update happened too long ago..?

            _logger.info("need to refresh key")
            j = self._get_or_refresh_key()

            kf.seek(0)
            print(j, file=kf)
            kf.truncate()  # in case new data was shorter
            kf.flush()
            self.key_modtime = os.fstat(fd).st_mtime
            fcntl.flock(fd, fcntl.LOCK_UN)  # happens automatically at close anyway

        self.key = json.loads(j)
        self.key_expiry = self.key_modtime + self.key["expires_in"] - 30

    def get(self, command: str) -> dict:
        """Perform a get on an api leaf.
        Return the output as a dictionary.
        """
        self.check_key_expiry()
        url = self.api_url + "/" + command
        headers = {"Authorization": "Bearer " + self.key["access_token"]}
        r = self.session.request("GET", url, headers=headers, timeout=30)
        r.raise_for_status()
        # print(r.text)
        return json.loads(r.text)

    def patch(self, name: str, **payload) -> None:
        """Perform a patch on a management id
        Additional keyword parameters are sent as the body payload.
        """
        if self.device is None:
            raise ValueError("need to configure device")
        self.check_key_expiry()
        url = f"{self.api_url}/gateway-devices/{self.device}/management-points/{name}"
        headers = {"Authorization": "Bearer " + self.key["access_token"]}
        r = self.session.request("PATCH", url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()

    def management_points(self):
        """Return the "managePoints" from the first gateway device.

        The raw output from gateway-devices contains an array of managementPoints
        but it's convenient to access them by their type, so pack them into
        a dictionary, keyed on "embeddedId", which are things like "climateControlMainZone"
        or "domesticHotWaterTank".
        """

        gw = self.get("gateway-devices")

        # assume there's just one gateway device

        if self.device is None:
            # no device configured - stash the id of the first gateway
            # for later
            self.device = gw[0]["id"]
            _logger.info("gateway device id is %s", self.device)

        return {item["embeddedId"]: item for item in gw[0]["managementPoints"]}

    def set_temperature_control(self, name, value):
        """Patch a temperature control = either "roomTemperature" or "leavingWaterOffset" """
        self.patch(
            "climateControlMainZone/characteristics/temperatureControl",
            path="/operationModes/heating/setpoints/" + name,
            value=value,
        )


    def set_powerful_mode(self, state):
        """Turn water immersion heater on or off"""
        self.patch(
            "domesticHotWaterTank/characteristics/powerfulMode",
            value = "on" if state else "off"
        )

def main():
    """Entry point if invoked as a script"""

    if len(sys.argv) == 1 or sys.argv[1] == "help":
        print(
            f"Usage: {sys.argv[0]} code [token] |refresh | get XXX | sensors | mp | debug | temp [value] | lwo [value] | powerful [0|1]"
        )
        return

    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    daikin = Daikin()

    if sys.argv[1] == "code":
        # this is used to bootstrap the authentication system.
        # Invoked with just code, it prints the url need to paste
        # into your browser to authenticate. That will result
        # in the browser being redirected to your nominated url,
        # with the default one just displaying it in the window.
        #
        # You can then re-invoke with code and add this value.

        if len(sys.argv) == 2:
            print(
                "To generate a new code, open brower with this url, then reinvoke and add the new code as a parameter\n"
            )
            print(
                f"{daikin.idp_url}/authorize"
                "?response_type=code"
                "&scope=openid%20onecta:basic.integration"
                f"&client_id={daikin.app['id']}"
                f"&redirect_uri={daikin.redir}"
            )
        else:
            # we have a new code - need to turn it into credentials
            daikin.get_new_key(code=sys.argv[2])

    elif sys.argv[1] == "refresh":
        # refresh the key if necessary.
        # Should happen automatically, so don't really need to
        # do it explicitly.
        daikin.get_or_refresh_key()

    elif sys.argv[1] == "sensors":
        mp = daikin.management_points()

        sd = mp["climateControlMainZone"]["sensoryData"]["value"]
        lwt = sd["leavingWaterTemperature"]["value"]
        outdoor = sd["outdoorTemperature"]["value"]
        room = sd["roomTemperature"]["value"]

        tc = mp["climateControlMainZone"]["temperatureControl"]["value"]
        # should this be "auto", or "heating" ?
        target = tc["operationModes"]["auto"]["setpoints"]["roomTemperature"]["value"]

        hwt = mp["domesticHotWaterTank"]["sensoryData"]["value"]
        hw = hwt["tankTemperature"]["value"]
        print(f"outdoor={outdoor}, room={room} / {target}, hw={hw}, lwt={lwt}")

    elif sys.argv[1] == "get":
        if len(sys.argv) == 2:
            print("Usage: get info | sites | gateway-devices | ...")
            return

        # perform a GET on an API url
        d = daikin.get(sys.argv[2])
        print(json.dumps(d, indent=4))

    elif sys.argv[1] == "mp":
        mp = daikin.management_points()
        print(json.dumps(mp, indent=4))

    elif sys.argv[1] == "temp":
        temp = float(sys.argv[2])
        daikin.set_temperature_control("roomTemperature", value=temp)

    elif sys.argv[1] == "lwo":
        lwo = int(sys.argv[2])
        daikin.set_temperature_control("leavingWaterOffset", value=lwo)

    elif sys.argv[1] == "powerful":
        state = int(sys.argv[2])
        daikin.set_powerful_mode(state)

    elif sys.argv[1] == "debug":
        print(json.dumps(daikin.app, indent=4))
        print(json.dumps(daikin.key, indent=4))
        now = time.time()
        if now < daikin.key_expiry:
            delta = daikin.key_expiry - now
            print(f"key expires in {delta} seconds")
        else:
            ago = now - daikin.key_expiry
            print(f"key expired {ago} seconds ago")

    else:
        print("Unknown request: ", sys.argv[1])


if __name__ == "__main__":
    main()
