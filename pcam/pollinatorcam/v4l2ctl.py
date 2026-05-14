import re
import subprocess


def usb_bus_to_id(bus_string):
    return bus_string.split('-')[-1].replace('.', '_')


def get_device_info():
    o = subprocess.check_output(['v4l2-ctl', '--list-devices']).decode('ascii')
    # output contains names (and busses)
    # followed by devices (on new lines) then a blank line
    device_name = None
    device_info = []
    for l in o.splitlines():
        # skip blank lines
        if len(l.strip()) == 0:
            continue
        
        # if this is a device name, add to devices
        if '/dev/' in l:
            if len(device_info) == 0:
                raise Exception(
                    "Failed to parse v4l2-ctl output, missing device name")
            device_info[-1]['devices'].append(l.strip())
        else:  # not a device line and not blank so this is the next name and bus
            # parse info line into name and bus
            device_name = re.search('(.*)\(', l).groups()[0].strip()
            # get bus in form: usb-0000:01:00.0-1.4.3.4'
            bus = re.search('\((.*)\)', l).groups()[0]
            device_info.append({
                'name': device_name,
                'info': l,
                'devices': [],
                'bus': bus,
                'id': usb_bus_to_id(bus),
            })
    return device_info


def find_device_info(locator):
    info = get_device_info()
    if '/dev/video' in locator:
        for i in info:
            if locator in i['devices']:
                return i
    else:  # assume a bus path/id
        for i in info:
            if i['id'] == locator:
                return i
    raise Exception("Failed to find info for device[%s] in %s" % (locator, info))
