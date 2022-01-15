Introduction
============

Purpose
-------

This project / repository contains a Python script and description on how to make the [UniFi Security Gateway](https://www.ui.com/unifi-routing/usg/) DNS service automatically resolve aliases (and only aliases) specified in the UniFi controller.

**This means you only have to define a client alias in the UniFi UI and the DNS server is automatically updated with that entry!**

Rationale
---------

The UniFi Security Gateway is a neat little device and it is very powerful. You can customise most of it, however it has one tiny flaw. The DNS service on the router will (by default) automatically add hostnames of the DHCP leases to its hosts file. This means, the DHCP clients decide what name they get in the DNS - which isn't very clever, nor is it secure.

We thought we can override that by simply specifying aliases in the UniFi controller. However, this is just for cosmetics and the UniFi Security Gateway won't use these aliases as hostnames for the DNS service. In fact, by introspecting the config on the USG we found out, that the UniFi controller doesn't even provision these aliases to the USG.

Design / Architecture
---------------------

We had similar issues on the [Edge Routers](https://www.ui.com/edgemax/edgerouter-x-sfp/) and could solve it quite simple, by parsing the static mappings of the config and converting them to a proper ``hosts`` file (see [edgerouter-dnsmasq-updater](https://github.com/confirm/edgerouter-dnsmasq-updater)). 

However, the USG won't have these informations as the aliases will never be propagated to the USG config. Thus, the USG needs to query the UniFi controller for these informations. Fortunately, the UniFi controller has an API which can be queried.

The final solution design is quite simple: 

A Python script is installed on the USG. It runs periodically, fetches all the clients found in the UniFi controller, updates a ``hosts`` file and reloads the DNS server when changes are detected.

Installation, Configuration & Usage
===================================

CLI Script
----------

The CLI script can be installed on the USG like this:

```
# Install script in /config/scripts to make it persistent over updates.
sudo curl -o /config/scripts/usg-easy-dns.py https://raw.githubusercontent.com/confirm/USG-Easy-DNS/master/usg-easy-dns.py

# Make script executable.
sudo chmod u+x /config/scripts/usg-easy-dns.py
```

The CLI script has a help flag (`-h`, ``--help``):

```
usage: usg-easy-dns.py [-h] [-u USERNAME] [-p PASSWORD] [-f FILE] [-i] [-d] url

USG Easy DNS script.

positional arguments:
  url                               the URL of the UniFi controller

optional arguments:
  -h, --help                        show this help message and exit
  -u USERNAME, --username USERNAME  UniFi username
  -p PASSWORD, --password PASSWORD  UniFi password
  -f FILE, --file FILE              the hosts file
  -i, --insecure                    skip SSL verification
  -d, --debug                       activate debug mode
```

The script is written in Python 2 and uses only the standard library, which means it has no external dependencies. You can run the script for test on any machine with Python 2 installed, for example:

```
./usg-easy-dns.py -u "my-username" -p "my-password" -f "/tmp/hosts" https://my-unifi-controller:8443
```

**IMPORTANT NOTES:** 

- The default credentials used by the script are ``usg/usg``.
- A separate user should be created on the UniFi controller. Read access is enough.
- The ``/etc/hosts`` file is managed by the USG itself, thus an alernative path is recommended.
- The script will store the new hosts file by default in ``/config/user-data/hosts``, since the ``/config/user-data`` directory won't be affected or deleted during / after an upgrade.

Task Scheduler
--------------

The USG has a task scheduler (i.e. cron), which can be used to run the script automatically. On the USG CLI the following configuration can be used:

```
set system task-scheduler task update-static-hosts crontab-spec "* * * * *"
set system task-scheduler task update-static-hosts executable path /config/scripts/usg-easy-dns.py
set system task-scheduler task update-static-hosts executable arguments -u "my-username" -p "my-passwod" https://my-unifi-controller:8443
```

DNS Configuration
-----------------

Of course the DNS server needs to be informed about this new file as well. Here's an example for that configuration:

```
# Don't use the default /etc/hosts file.
set service dns forwarding options no-hosts

# Use /config/user-data/hosts instead.
set service dns forwarding options addn-hosts=/config/user-data/hosts 

# Never forward plain names (without a dot or domain part).
set service dns forwarding options domain-needed

# Never forward addresses in the non-routed address spaces.
set service dns forwarding options bogus-priv

# Add the domain to hostname lookups without a domain.
set service dns forwarding options expand-hosts
set service dns forwarding options domain=<your domain>

# Don't forward the local domain.
set service dns forwarding options local=/<your domain>/
```

Config Persistence
------------------

**Please note, changing the configuration on the CLI directly is not persistent over USG upgrades.**

If you want to make this persistent, you've to add the configuration to the ``config.gateway.json``. There's a helpful article called [UniFi - USG Advanced Configuration Using config.gateway.json](https://help.ui.com/hc/en-us/articles/215458888-UniFi-USG-Advanced-Configuration) which describes this perfectly.
