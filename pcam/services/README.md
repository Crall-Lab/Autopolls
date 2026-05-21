Program execution is managed by systemd with the following services

1) pcam-discover
1) tfliteserve
1) pcam@  [a templated service based on camera ip]


tfliteserve
-----

tfliteserve runs the the NN detection server process


pcam-discover
-----

pcam-discover scans the local network (default range based on eth0 ip).
For each camera found (based on a valid return of dahuacam.get_name) a
templated service is started pcam@specific_camera_ip
pcam-discover will store scan results in /dev/shm/pcam/ips.json
and scans can be hard coded in ~/.pcam/ips.json
To disable an ip, add the following to the hard coded json:

```json
{'192.168.0.120': false}
```

Multiple ips should be added to the same dictionary). To force enabling
(bypass the network scan results for an ip) use true instead of false


Usage Notes
-----

All of these services can be checked using standard systemd commands:

```bash
# to check the status of pcam-discover
sudo systemctl status pcam-discover

# or a specific camera
sudo systemctl status pcam@192.168.0.120

# or get the journal entries for a service
sudo journalctl -au pcam-discover

# to stop a service (see note below)
sudo systemctl stop pcam@192.168.0.120
# this will get restarted by pcam-discover unless the ip is disabled

# to see what camera services are active
sudo systemctl list-units | grep pcam@
```

None of these services provide the initial configuration (see
dahuacam.initial_configuration and set_snap_config).

Most of these services write logs to /mnt/data/logs. Note that these writes
are buffered so they will not appear in real-time.

Installation Notes
-----

The above services will need to be:

1) configured (mainly setting paths)
1) services symlinked into /etc/systemd/system/
1) enable pcam-discover and tfliteserve [to run automatically on boot]
1) start pcam-discover and tfliteserve [or just reboot]
