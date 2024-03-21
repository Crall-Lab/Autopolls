import re
import subprocess
import cv2 as cv
import json
import time
import numpy as np
import argparse


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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-t', '--time', default=10,
        help='input a duration for video, 10sec default')
    parser.add_argument(
        '-f', '--focus', default=None,
        help='input a duration for video, 10sec default')
    tlapse = parser.parse_args().time
    f1 = parser.parse_args().focus
    if f1 == None:
        customSetting = '/home/pi/Desktop/configs'
        in1 = open(customSetting,'r')
        settingsL = json.load(in1)
        in1.close()
        f1 = settingsL['focus']
    else:
        f1 = float(f1)
    allDevices = get_device_info()
    usbOnly = []
    for ele in allDevices:
        if 'usb' in ele['bus']:
            usbOnly.append(ele)

    fAdjust = getattr(cv,'CAP_PROP_FOCUS')
    aStreams = {}
    for cams in usbOnly:
        subprocess.check_output(['sudo','systemctl','stop','pcam@'+cams['id']]).decode('ascii')
        vidID = cams['devices'][0]
        aStreams[vidID] = []
        aStreams[vidID].append(cv.VideoCapture(vidID))
        aStreams[vidID][0].set(fAdjust,f1)
        aStreams[vidID].append(int(cams['id'][-3]))
        aStreams[vidID].append(cams['id'])
    time.sleep(0.5)
    baseIm = np.zeros((600,800,3))
    inds = [(0,0),(0,400),(300,0),(300,400)]

    t1 = time.time()
    t2 = time.time()
    while t2-t1 < float(tlapse):
        for cT in aStreams.keys():
            readIn,frame = aStreams[cT][0].read()
            r1 = cv.resize(frame,((400,300)))
            tXY = inds[aStreams[cT][1]-1]
            baseIm[tXY[0]:tXY[0]+300,tXY[1]:tXY[1]+400] = r1
            
        cv.putText(baseIm,'Cam1',(35,35),0,1,(255,255,255),2)
        cv.putText(baseIm,'Cam2',(420,35),0,1,(255,255,255),2)
        cv.putText(baseIm,'Cam3',(20,320),0,1,(255,255,255),2)
        cv.putText(baseIm,'Cam4',(440,320),0,1,(255,255,255),2)
        cv.imshow('test',baseIm.astype(np.uint8))

        cv.waitKey(50)
        t2 = time.time()
        
    for cT in aStreams.keys():
        aStreams[cT][0].release()
        subprocess.check_output(['sudo','systemctl','start','pcam@'+aStreams[cT][2]]).decode('ascii')
        print('systemctl start pcam@%s'%aStreams[cT][2])

main()