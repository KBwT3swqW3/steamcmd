# Description
Python library so that I can install/manage/configure steamcmd installed dedicated
servers in a standardised way.

Also allows for installing Systemd services to run the servers and binds their
stdin's to a unix socket for sending commands to the servers consoles. This is
used by the systemd module that's part of this library to cleanly shut down the
servers on a systemctl stop service.

It's assumed that steamcmd is already installed and is running as the steam user,
though there are flags to change this they're untested.

Note: If you've managed to find this repo which is mostly for my own use, I am in 
no way affiliated with Steam or Valve

# Table of Contents
- [Description](#description)
- [Table of Contents](#table-of-contents)
- [Installation](#installation)
- [Usage](#usage)
  - [Create/Update a Server + Sourcemod, Install Collections and Configure Server](#createupdate-a-server--sourcemod-install-collections-and-configure-server)
  - [Install Systemd files](#install-systemd-files)

# Installation

```sh
steam@server:~$ python3 -m venv /home/steam/.venv
steam@server:~$ source .venv/bin/activate
(.venv) steam@server:~$ pip install https://github.com/KBwT3swqW3/steamcmd/releases/download/refs%2Fheads%2Fgithub-actions-build/steamcmd.tar.gz
```

# Usage

## Create/Update a Server + Sourcemod, Install Collections and Configure Server

```py
#!/home/steam/.venv/bin/python
from steamcmd.left4dead2 import Left4Dead2Server
import logging

logging.getLogger("steamcmd").addHandler(logging.StreamHandler())
logging.getLogger("steamcmd").setLevel("INFO")

server = Left4Dead2Server()
server.install_app(collection_ids=[123456, 654321])
server.create_sourcemod_groups(
    [
        {
            "name": "SuperAdmins",
            "permissions": "z",
            "immunity": "999",
        },
        {
            "name": "Admins",
            "permissions": "abcdefghijklm",
            "immunity": "100",
        },
    ]
)
server.create_sourcemod_admins(
    [
        {"username": "STEAM_0:0:XXXXXXX", "group": "@SuperAdmins"},
        {"username": "STEAM_0:1:YYYYYYY", "group": "@Admins"},

    ]
)
server.update_server_cfg_settings(
    {
        "hostname": "My Server",
        "sv_gametypes": "both",
        "sv_steamgroup": 123456,
        "sv_steamgroup_exclusive": 1,
        "sv_allow_lobby_connect_only": 0,
        "sv_region": 3,
        "sv_cheats": 0,
        "sv_lan": 0,
        "sv_alltalk": 0,
        "sv_logfile": 1,
        "sv_logbans": 1,
        "sv_logecho": 1,
        "sv_log_onefile": 0,
        "sv_minrate": 20000,
        "sv_maxrate": 30000,
    }
)
```

```sh
(.venv) steam@server:~$ ./install-servers.py
```

## Install Systemd files

```py
#!/home/steam/.venv/bin/python
from steamcmd.left4dead2 import Left4Dead2Server
from steamcmd.systemd import systemd_reload

logging.getLogger("steamcmd").addHandler(logging.StreamHandler())
logging.getLogger("steamcmd").setLevel("INFO")

server = Left4Dead2Server()
server.install_systemd_service()

systemd_reload()
```

The above as root will create the below systemd files, and perform a daemon-reload
to start the servers run `systemctl start left4dead2-0` to automatically start the
service on boot `systemctl enable left4dead2-0`.

The 0 in the below is the default server reference you can set a server reference
when initializing the server objects by passing in the `server_ref` argument, this
is useful for when you want to create multiple servers of the same type, it allows
you to give them names.


```ini
# /etc/systemd/system/left4dead2-0.service
[Unit]
Description=Instance of left4dead2, reference: 0
After=left4dead2-0.socket
Requires=left4dead2-0.socket

[Service]
StandardInput=socket
StandardOutput=journal+console
User=steam
Group=steam
ExecStart=/home/steam/games/222860/0/srcds_run
ExecStop=/home/steam/.venv/bin/python -m steamcmd.systemd $MAINPID --cmd 'say Server shutting down in 10 seconds' --cmd 'quit' --cmd-delay 10

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/left4dead2-0.socket
[Unit]
Description=Socket for interacting with left4dead2, reference: 0
PartOf=left4dead2-0.service

[Socket]
ListenFIFO=/run/left4dead2-0.socket
SocketUser=steam
SocketGroup=steam
RemoveOnStop=yes

[Install]
WantedBy=sockets.target
```
