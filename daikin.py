#!/usr/bin/env python3

"""
A class to manage access to the Daikin Onecta cloud API.
Plus a simple CLI for getting the initial authentication
established, and testing.
"""

import json
import logging
import pathlib
import requests
import time
import sys

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

    # This is a trivial generic script running on a free hosting site.
    # It simply echos the 'code' parameter to the page, from which
    # you can paste it in - see 'code' in main().
    redir = "https://ibmx20.infinityfreeapp.com/daikin.php"

    # the json-formatted file containing the app details: the "id"
    # and the "secret"
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

        self.load_key_file()

        session = requests.Session()
        session.headers.update({"Accept-Encoding": "gzip"})
        self.session = session

    def load_key_file(self) -> None:
        """Load the key file, and calculate expiry time"""
        try:
            with self.key_file.open() as kf:
                self.key = json.load(kf)

            # we store the modtime so that we can detect if
            # another process has updated it since we loaded it
            self.key_modtime = self.key_file.stat().st_mtime
            self.key_expiry = self.key_modtime + self.key["expires_in"] - 30
        except FileNotFoundError:
            _logger.error(
                "cannot load keys file - you'll need to go through the interactive authentication process"
            )
            self.key = dict()
            self.key_modtime = 0
            self.key_expiry = 0

    def get_or_refresh_key(self, code=None) -> None:
        """Generate or refresh access token.

        If code is supplied, it is taken as being a new code from
        an interactive authentication. Otherwise we are just using
        the refresh token from an expired key."""

        args = {"client_id": self.app["id"], "client_secret": self.app["secret"]}
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
        r = requests.post(url)
        r.raise_for_status()
        j = r.text
        with self.key_file.open(mode="w") as keys:
            print(j, file=keys)
        self.key = json.loads(j)
        self.key_modtime = self.key_file.stat().st_mtime
        self.key_expiry = self.key_modtime + self.key["expires_in"] - 30

    def check_key_expiry(self) -> None:
        """Check whether key has expired, and try to update if necessary."""
        now = time.time()
        if now < self.key_expiry:
            # still good.
            return

        modtime = self.key_file.stat().st_mtime
        if modtime > self.key_modtime:
            # seems that another process has already updated the file
            self.load_key_file()
            if now < self.key_expiry:
                # new key is good
                return

        _logger.info("need to refresh key")
        self.get_or_refresh_key()

    def get(self, command: str) -> dict:
        """Perform a get on an api leaf.
        Return the output as a dictionary.
        """
        self.check_key_expiry()
        url = self.api_url + "/" + command
        headers = {"Authorization": "Bearer " + self.key["access_token"]}
        r = self.session.request('GET', url, headers=headers)
        r.raise_for_status()
        # print(r.text)
        return json.loads(r.text)


def main():
    """Entry point if invoked as a script"""

    if len(sys.argv) == 1:
        print(f"Usage: {sys.argv[0]} code [token]|refresh|get XXX|sensors|debug")
        return

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
            daikin.get_or_refresh_key(code=sys.argv[2])

    elif sys.argv[1] == "refresh":
        # refresh the key if necessary.
        # Should happen automatically, so don't really need to
        # do it explicitly.
        daikin.get_or_refresh_key()

    elif sys.argv[1] == "sensors":
        # This is a bit higher-level than I had intended for
        # main() - really ought to be in a separate script

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
        print(f"outdoor={outdoor}, room={room}, hw={hw}, lwt={lwt}")

    elif sys.argv[1] == "get":
        if len(sys.argv) == 2:
            print("Usage: get info | sites | gateway-devices | ...")
            return

        # perform a GET on an API url
        d = daikin.get(sys.argv[2])
        print(json.dumps(d, indent=4))

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
