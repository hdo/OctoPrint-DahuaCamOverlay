# OctoPrint-DahuaCamOverlay

This plugin add print status information to Dahua surveillance cameras as text overlay via Dahua HTTP API.

## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/hdo/OctoPrint-DahuaCamOverlay/archive/master.zip


## Configuration

Create dedicated user within Dahua Web-Frontend. The user has to have the admin role with 'Video/Audio' permission set.

The user credentials needs to be configured on the plugin configuration page.

Example:

```
Host: 192.168.2.32
User: <username>
Password: <password>
Use M73 info: <checkbox>
```

With M73 checked the plugin will use progress information inside the G-Code. [PrusaSlicer](https://help.prusa3d.com/en/article/prusa-specific-g-codes_112173) is using this G-Code command which is quiet accurate.


