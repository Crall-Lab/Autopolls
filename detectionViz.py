#%%
import json
import sys
import cv2 as cv
import os
from matplotlib import pyplot as plt
import numpy as np
import matplotlib
import glob
# %%
base = '/mnt/data/detections/'

try:
    input1 = str(sys.argv[1])
except Index/mnt/data/'+det['meta']['still_filename'].split('mnt/data/')[1]
im1 = cv.imread(fileName)
image1 = cv.cvtColor(cv.imread(fileName),cv.COLOR_BGR2RGB)
sz1 = np.shape(image1)
fig,ax = plt.subplots()


for bb in det['meta']['bboxes'][0][0]:
    if bb[1] > 0.35:
        xy1 = (bb[2][0]*sz1[0],bb[2][1]*sz1[1])
        xy2 = (bb[2][2]*sz1[0],bb[2][3]*sz1[1])
        h1 = xy2[0]-xy1[0]
        w1 = xy2[1]-xy1[1]
        
        xy1 = [xy1[1],xy1[0]]
        rect = matplotlib.patches.Rectangle(xy1,w1,h1,linewidth=4,edgecolor='r',facecolor='none')
        ax.add_patch(rect)
plt.imshow(image1)
plt.show()
plt.savefig('/home/pi/Desktop/preview.jpg')Error:
    getCams = os.listdir(base)
    input1 = getCams[0]

ft = glob.glob(base+input1+'/*')
ft.sort()

dets = glob.glob(ft[-1]+'/*')
dets.sort()
lastDets = dets[-1]

in1 = open(lastDets,'r')
det = json.load(in1)
# %%

fileName = '/mnt/data/'+det['meta']['still_filename'].split('mnt/data/')[1]
im1 = cv.imread(fileName)
image1 = cv.cvtColor(cv.imread(fileName),cv.COLOR_BGR2RGB)
sz1 = np.shape(image1)
fig,ax = plt.subplots()


for bb in det['meta']['bboxes'][0][0]:
    if bb[1] > 0.35:
        xy1 = (bb[2][0]*sz1[0],bb[2][1]*sz1[1])
        xy2 = (bb[2][2]*sz1[0],bb[2][3]*sz1[1])
        h1 = xy2[0]-xy1[0]
        w1 = xy2[1]-xy1[1]
        
        xy1 = [xy1[1],xy1[0]]
        rect = matplotlib.patches.Rectangle(xy1,w1,h1,linewidth=4,edgecolor='r',facecolor='none')
        ax.add_patch(rect)
plt.imshow(image1)
plt.show()
plt.savefig('/home/pi/Desktop/preview.jpg')
