"""
Checks for a text file written by cvcapture that contains v4l2 camera settings
Reads and runs commands using subprocess
Then edits the file to remove each command executed
"""

import subprocess
import os
import time

def run():
    s_path = os.path.join(os.path.expanduser('~'), 'Autopolls', 'pcam','v4l2_list.txt')
    
    # pause to let pcam-discover ID USB cameras and write commands to v4l2
    time.sleep(8)

    # read command list
    in1 = open(s_path,'r')
    dd = in1.readlines()
    in1.close()


    # for line in command list
    for ee in dd:
        # remove line split
        ee = ee.split(' \n')[0]
        # execute in bash
        ooo = subprocess.Popen(ee.split(' '))

    # read in commands again in case of modification while script is running
    in1 = open(s_path,'r')
    dde = in1.readlines()
    in1.close()

    # populate list with executed commands and remove from the file
    o = []
    for e in dde:
        ap = False
        for ee in dd:
            if e != ee:
                continue
            else:
                ap = True
        if not ap:
            o.append(e)

    # write any new commands to the list or empty the file
    in1 = open(s_path,'w')
    for ee in o:
        in1.write(ee)
    in1.close()

if __name__ == '__main__':
    run()