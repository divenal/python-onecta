# python-onecta
python class to connect to Daikin Onecta cloud interface

See also https://github.com/jwillemsen/daikin_onecta which is a Home Assistant
integration, and https://github.com/Apollon77/daikin-controller-cloud which is
similar but in javascript or typescript or some-such. (I wasn't really sure what
to do with that.)

I don't currently use Home Assistant, so prefer CLI-based tools, and trying to
learn python at the same time.

See those other projects for more of the background on getting yourself setup,
and of course the daikin api docs themselves at
https://developer.cloud.daikineurope.com/ (requires a daikin login).

Assuming you've already got the Onecta app running on a phone, you should already have login details.

The python script requires third-party library
`requests` from pip, but is otherwise just standard python3. Only tested on
linux, though. The paths for the configuration and key file might need to be
changed for windows. (See top of the class in daikin.py)

## Authentication and the redirect url

There are three steps to the initial authorisation process:
1. use browser to connect to a specially-encoded url
2. click on the agree button which generates a code
3. turn the code into an access token.

The script can generate the correct url for step 1, and then take care of step 3.

A slightly confusing aspect of the authenication process is the need for a redirection url.
When you authenticate your app, your browser will be directed to this url with a generated code.
I assume the idea is that the server that hosts this url will store the code away somewhere.
(There's another variable you can also supply which I guess stores some additional context, but I'm not using that.)

The URL has to be https. I'm not quite sure if it has to be accessible from the internet (ie if you need port-forwarding on your router to run
it on home network) - I did get that set up, but not sure it's needed.

But I now have a much simpler solution: on a free-hosting site I have for other stuff, I've set up
a trivial php script - all it does is echo the `?code=...` from the url into the text.
You're welcome to use that as your redirect url. (I usually remember to update the certificate,
but it may work even after they've expired if you force your browser...)

I don't record any codes sent, though they might show up in the access logs that I don't have access to. But the code is useless
without the app id and secret, which I won't have access to anyway.

The url is https://ibmx20.infinityfreeapp.com/daikin.php

If you use something different, you'll have to modify the `redir` near the top of the source file.
(The app needs to send the url from time to time, and it needs to match the one stored on the "app".)


## Create an app with redirect url
The first thing you need to do is create an app on the website. Well, they call it an app, but it's little more than a name to identify some tokens.

In the drop-down menu at top right, choose "My Apps", and create one.
You have to give it the url redirect as above. (Note that the app has to send this url from
time to time, so it has to match.)


So once you've put that into the web page, you can "proceed" to create the app. It will print an `id` and a `secret` that you will need to copy.

## Create local config file
The script loads a config file during startup to get the app details. Currently expects it to be in `~/.daikin_app.json`

That should be json-formatted, like
```
{
  "id": "XXX",
  "secret": "YYYYY"
}
```

If you want to be able to make changes using the scripts, you can add a third field "device" - you can find
the value you need once you've got the basic functionality working.

## Authenticate the app to use your daikin system.

Invoke the python script with a single parameter `code`. That will print out the url you need to open to authenticate the app.
That should bring up a page telling you about the app, and invite you to "agree".  If you do, it will forward the browser to the
redirect script which, assuming you're using my php script, will just show the code on the page.

Copy that code, then invoke the python script again with `code` followed by this (very long) code. The script will then
connect to the daikin id system and generate an access token, which it will store in a file.

And that should be it done.  The token only lasts for an hour, but the script should automatically refresh it as required.

The authentication lasts a year - you'll have to do this manual step again then.

Or if you lose the file containing the key, you'll have to start again.

## Test

Invoke the script with `get info` to get basic information, or `get gateway-devices` to see all your devices.

Invoke with `sensors` to show a snapshot of the few temperatures it makes available.

Or 'debug' shows the config, including remaining lifetime of the access token.

## Making changes with the API

As mentioned above, you'll have to add a "device" to the config file to make changes.
You can get this using  `get sites` which will output


```
[
    {
        "_id": "XXX-YYYY-ZZZZ",
        "id": "XXX-YYYY-ZZZZ",
        "gatewayDevices": [
          "AAAA-BBB-CCC"
        ],
        ...
    }
]
```

Or you can also get the gatewayDevice id from  `get gateway-devices`.

These scripts assume only one device

The scripts could possibly issue a `get sites` automatically if you've not conifugured a site.

## Problems

There is a potential problem if you have multiple scripts sharing the key - if they
decide to refresh at the same time, they will clash and may well corrupt the
key/refresh token, which means you'll have to start again. The script does use
file locking which is intended to reduce this risk, but I've not tested it
aggressively, so I can't be sure it actually works...

## daikin-monitor.py

This is a script that prints out the sensor temperatures every 10 minutes.

Output looks like

```
2024-10-25--00-05: outdoor=13 room=20.3 / 20.5 hw=38 lwt=20 (offs=0)
2024-10-25--00-15: outdoor=13 room=20.4 / 20.5 hw=38 lwt=23 (offs=0)
2024-10-25--00-25: outdoor=12 room=20.4 / 20.5 hw=34 lwt=37 (offs=0)
...
```

where second number after room is the target temperature, and
offs is the 'leaving water offset' which can be set via app
or API (to tweak the lwt).

I actually run a slightly modified version which also displays the
the power consumption as measured by a CT clamp monitored by my Zappi charger.

## daikin-consumption.py

Fetches and outputs recent consumption figures. Assumption is that
you want complete period, so it shows yesterday or last week,
rather than in-progress today or this week.

I invoke it from cron every morning to record daily results,
and every monday morning to record weekly results.
