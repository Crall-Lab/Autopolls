"""
Periodically (every 10 minutes?) scan network
    Find ips on network (some may be previously saved)
    Attempt connection to ip as camera
        If camera, start systemd service, record ip as camera
        If not camera, record ip as not camera

Keep track of:
    Connection

Cache format: key = ip, value = name (if camera), False if not camera

if ip is in base_filename, don't pay attention to scan results
    if true or name: start/make sure service is running
    if false: ignore
if ip is not in base, check config
    if true or name: start/make sure service is running
    if false: ignore
when a new ip is found, check if it's a camera and add it to the config
"""

import argparse
import json
import logging
import os
import re
import subprocess
import time

from . import config
from . import dahuacam
from . import v4l2ctl


default_cidr = '10.1.1.0/24'
ip_regex = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
cfg_name = 'ips.json'
# dictionary where keys=ips, value=dict
#   is_camera=True/False
#   is_configured=True/False
#   name=camera name (if a camera)
#   service={Active: True/False, UpTime: N}
#   skip=True/False (if not present, assume false)


def get_cameras():
    cfg = config.load_config(cfg_name, None)
    if cfg is None:
        return {}
    return {
        ip: cfg[ip]['name'] for ip in cfg
        if cfg[ip]['is_camera'] and cfg[ip]['is_configured']}


def scan_network_for_ips(cidr=None):
    if cidr is None:
        cidr = default_cidr
    cmd = "nmap -nsP {cidr}".format(cidr=cidr).split()
    logging.debug("Running scan command: %s", cmd)
    o = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
    logging.debug("Parsing scan command output")
    for l in o.stdout.decode('ascii').splitlines():
        logging.debug("Parsing line: %s", l.strip())
        ms = ip_regex.findall(l)
        if len(ms):
            logging.debug("Scan found ip: %s", ms[0])
            yield ms[0]


def check_if_camera(ip):
    """Check if the provided ip is a configured camera
    Returns:
        is_camera
        is_configured
        camera name
    """
    logging.debug("Checking if ip[%s] is a camera", ip)
    dc = dahuacam.DahuaCamera(ip)
    try:
        n = dc.get_name()
        logging.debug("Camera returned name: %s", n)
        mn = dahuacam.mac_address_to_name(dc)
        if len(n) != 12:
            logging.error("Camera name isn't 12 chars")
            return True, False, n
        logging.debug("Camera name from mac: %s", mn)
        if mn != n:
            logging.error(
                "Camera %s isn't configured: %s != %s" % (ip, n, mn))
            return True, False, n
        return True, True, n
    except Exception as e:
        logging.debug("IP returned error: %s", e)
        return False, False, ''


def start_camera_service(ip):
    # compute systemd service name
    name = 'pcam@%s' % ip
    logging.info("Service %s not running, starting...", name)
    # not running, try starting
    cmd = 'sudo systemctl start %s' % name
    o = subprocess.run(cmd.split(), check=True)


def verify_camera_service(ip):
    # compute systemd service name
    name = 'pcam@%s' % ip
    logging.debug("Checking status of %s service", name)

    # check if service is running
    cmd = 'sudo systemctl is-active %s --quiet' % name
    logging.debug("Running %s", cmd)
    o = subprocess.run(cmd.split())
    logging.debug("Return code %i", o.returncode)
    if o.returncode != 0:
        logging.info("Service %s not running, starting...", name)
        # not running, try starting
        cmd = 'sudo systemctl start %s' % name
        try:
            o = subprocess.run(cmd.split(), check=True)
            return True
        except Exception as e:
            logging.error("Failed to start service %s: %s", name, e)
            return False
    else:
        return True


def verify_nas_config(ip):
    logging.debug("Checking NAS config for %s", ip)
    dc = dahuacam.DahuaCamera(ip)
    nas_ip = dc.get_config('NAS[0].Address').strip().split('=')[1]
    logging.debug("NAS host ip = %s", nas_ip)
    hip = dahuacam.get_host_ip(ip)
    if nas_ip != hip:
        logging.info("Setting NAS host ip to %s for %s", hip, ip)
        dahuacam.set_snap_config(
            dc, {'user': 'ipcam', 'enable': True, 'ip': hip})


def status_of_all_camera_services():
    cmd = (
        "sudo systemctl show "
        "--property=Id,ActiveState,ActiveEnterTimestampMonotonic pcam@*")
    o = subprocess.run(cmd.split(), stdout=subprocess.PIPE, check=True)
    cams = {}
    cam_ip = None
    t = time.monotonic()
    for l in o.stdout.decode('ascii').splitlines():
        if len(l.strip()) == 0:
            continue
        k, v = l.strip().split("=")
        if k == 'Id':
            cam_ip = '.'.join(v.split('@')[1].split('.')[:-1])
            cams[cam_ip] = {}
        elif k == 'ActiveState':
            cams[cam_ip]['Active'] = v == 'active'
        else:
            cams[cam_ip]['Uptime'] = t - int(v) / 1000000.
    return cams


def check_cameras(cidr=None):
    # dictionary where keys=ips, value=dict
    #   is_camera=True/False
    #   is_configured=True/False
    #   name=camera name (if a camera)
    #   service={Active: True/False, UpTime: N}
    #   skip=True/False (if not present, assume false)
    cfg = config.load_config(cfg_name, {})
    network_ips = list(scan_network_for_ips(cidr))
    services = status_of_all_camera_services()

    # add old cameras to network_ips
    for ip in cfg:
        if cfg[ip].get('skip', False):
            continue
        if not cfg[ip]['is_camera']:
            continue
        if ip not in network_ips:
            network_ips.append(ip)

    logging.debug("Found ips: %s", network_ips)
    logging.debug("Old ips: %s", list(cfg.keys()))
    logging.debug("Service ips: %s", list(services.keys()))
    # if we have to start a service, rescan after starting
    rescan_services = False
    new_cfg = {}
    # TODO error catching, save on error?
    for ip in network_ips:
        # is blacklisted?
        if ip in cfg and cfg[ip].get('skip', False):
            new_cfg[ip] = cfg[ip]
            continue

        is_camera, is_configured, name = check_if_camera(ip)
        cam = {
            'is_camera': is_camera,
            'is_configured': is_configured,
            'name': name,
        }

        # service running?
        cam['service'] = services.get(ip, {'Active': False, 'Uptime': 0})

        # verify nas config
        if is_camera and is_configured:
            verify_nas_config(ip)
            if not cam['service']['Active']:
                try:
                    start_camera_service(ip)
                    rescan_services = True
                except Exception as e:
                    logging.warning("Failed to start camera[%s]: %s", ip, e)
        new_cfg[ip] = cam

    # a service was started, rescan
    if rescan_services:
        logging.debug("Rescanning services")
        services = status_of_all_camera_services()
        for ip in services:
            if ip not in new_cfg:
                continue
            new_cfg[ip]['service'] = services[ip]


    config.save_config(new_cfg, cfg_name)


def check_v4l2_cameras():
    # load old config
    logging.debug("Loading old config from %s", cfg_name)
    cfg = config.load_config(cfg_name, {})

    # get a dictionary for each found device
    # this includes:
    # - name
    # - info
    # - devices
    # - bus
    # - id
    # with id being the most critical piece (this becomes the name)
    logging.debug("Getting v4l2 device information")
    device_info = v4l2ctl.get_device_info()
    logging.debug("\tv4l2 info: %s", device_info)

    # construct a new config with device names as keys and dict values with
    # - is_camera
    # - is_configured
    # - name
    # - service {Active, Uptime}
    new_cfg = {}
    rescan_services = False
    services = status_of_all_camera_services()
    for di in device_info:
        # TODO check if disabled in old config
        name = di['id']
        logging.debug("Checking %s", name)

        # TODO better 'video' detection
        is_camera = name not in ('codec', 'isp')  # ignore pi codec and isp
        is_camera = is_camera and any(('video' in d for d in di['devices']))
        logging.debug("\t is_camera? %s", is_camera)

        cam_cfg = {
            'name': name,
            'is_camera': is_camera,
            'is_configured': True,
            # fill in with actual service info
            'service': services.get(name, {'Active': False, 'Uptime': 0}),
        }

        # start service if not running
        if cam_cfg['is_camera'] and not cam_cfg['service']['Active']:
            logging.debug("Starting service for %s", name)
            try:
                start_camera_service(name)
                rescan_services = True
            except Exception as e:
                logging.warning("Failed to start camera[%s]: %s", name, e)

        new_cfg[name] = cam_cfg

    # if any services were started, rescan
    if rescan_services:
        logging.debug("Rescanning services")
        # TODO add a small delay to allow services to start?
        services = status_of_all_camera_services()
        for name in services:
            if name not in new_cfg:
                continue
            new_cfg[name]['service'] = services[name]

    # save config
    logging.debug("Saving confg to %s", cfg_name)
    config.save_config(new_cfg, cfg_name)


def cmdline_run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--ips', type=str, default="",
        help="ips to scan (as cidr)")
    parser.add_argument(
        '-p', '--print', action='store_true',
        help="print last discover results")
    parser.add_argument(
        '-u', '--usb', action='store_true',
        help="scan for usb (instead of ip) cameras")
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help="enable verbose logging")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.print:
        cfg = config.load_config(cfg_name, None)
        if cfg is None:
            print("No previous discover results found")
            return
        camera_ips = []
        other_ips = []
        for ip in cfg:
            if cfg[ip]['is_camera'] and cfg[ip]['is_configured']:
                camera_ips.append(ip)
            else:
                other_ips.append(ip)
        print("Cameras: %i" % len(camera_ips))
        for ip in sorted(camera_ips):
            cam = cfg[ip]
            print(
                "\t%s %s %s %s" % (
                    ip, cam['name'],
                    'up' if cam['service']['Active'] else 'DOWN',
                    cam['service']['Uptime']))
        print("Other devices: %i" % len(other_ips))
        for ip in sorted(other_ips):
            dev = cfg[ip]
            print("\tIP: %s" % ip)
            if dev['is_camera']:
                print("\tLikely an non-configured camera!!")
                print("\tName: %s" % cfg[ip]['name'])
        return

    # TODO verify cidr

    if len(args.ips):
        cidr = args.ips
    else:
        cidr = None

    #time running of check_cameras
    t0 = time.monotonic()
    if args.usb:  # search for usb/v4l2 devices instead of ip
        logging.debug("Scanning for v4l2 devices")
        check_v4l2_cameras()
    else:
        logging.debug("Scanning for ip devices")
        check_cameras(cidr)
    t1 = time.monotonic()
    logging.debug("check_cameras took %0.4f seconds", t1 - t0)


if __name__ == '__main__':
    cmdline_run()
