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
https://developer.cloud.daikineurope.com/docs/b0dffcaa-7b51-428a-bdff-a7c8a64195c0/introduction  (requires a daikin login).

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
