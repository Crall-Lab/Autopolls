"""
An autopolls function that will create and images with the infered bounding
The directory path to the unit should be included as the second argument 
after calling the script.
inputs: det1 - loaded json file
        Sdir - directory for saving
        Udir - directory path
        thresh1 - threshold to display or not display boxes
"""
#%%
import glob
from matplotlib import pyplot as plt
import matplotlib
import os
import cv2 as cv
import numpy as np
import json
import sys


# %%
def grabIm(det1,Sdir,Udir,thresh1):
    fname = Udir
    fileName = fname+det1['meta']['still_filename'].split('mnt/data/')[1]
    image1 = cv.cvtColor(cv.imread(fileName),cv.COLOR_BGR2RGB)
    sz1 = np.shape(image1)
    fig,ax = plt.subplots()
    
    bxCnt = 0
    for bb in det1['meta']['bboxes'][0][0]:
        if bb[1] >= thresh1:
            xy1 = (bb[2][0]*sz1[0],bb[2][1]*sz1[1])
            xy2 = (bb[2][2]*sz1[0],bb[2][3]*sz1[1])
            h1 = xy2[0]-xy1[0]
            w1 = xy2[1]-xy1[1]
            
            xy1 = [xy1[1],xy1[0]]
            rect = matplotlib.patches.Rectangle(xy1,w1,h1,linewidth=2,edgecolor=(0.9,0.3,0.5,0.85),facecolor='none')
            ax.add_patch(rect)
            bxCnt +=1
    if bxCnt > 0:         
        ax.imshow(image1)
        temps = det1['meta']['still_filename'].split('/')[-1]
        if os.path.isfile(Sdir+temps) == False:
            plt.savefig(Sdir+temps,dpi=350)

#%%
baseTemp = os.getcwd()+'/'
fldrName = 'detection'
thresh = 0.5

usbDir = str(sys.argv[1])
print('     #######################################################')
print('     #######################################################')
print('      Saving images to:  '+baseTemp+fldrName+'/')
print('     #######################################################')
print('     #######################################################')

if not os.path.isdir(baseTemp+fldrName+'/'):
    os.mkdir(baseTemp+fldrName+'/')
savePath = baseTemp+fldrName+'/'
cams = glob.glob(usbDir+'detections/*')
for cam in cams:

    tempTime = glob.glob(cam+'/*')
    for time1 in tempTime:
        
        tempDet = glob.glob(time1+'/*')
        for dets in tempDet:
            if os.path.getsize(dets) == 0:
                continue
            in1 = open(dets,'r')
            try:
                out = json.load(in1)
            except UnicodeDecodeError:
                print('unicode error skip')
                continue
            in1.close()
            if out.get('meta') != -1 and out['meta'].get('detections') != [[]]: 
                if out['meta']['detections'][0][0][1] > thresh:
                    temps = baseTemp+fldrName+'/'+out['meta']['still_filename'].split('/')[-1]
                    if os.path.isfile(temps):
                        continue
                    grabIm(out,savePath,usbDir,thresh)
# %%
