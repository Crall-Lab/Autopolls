#!/bin/bash

source $HOME/.virtualenvs/autopolls/bin/activate

cd $HOME/AP/tfliteserve

# Read in model options
CLASSES=`cat /home/pi/Desktop/configs | jq '.classes'`
CORAL=`cat /home/pi/Desktop/configs | jq '.coral'`

if [[ $CLASSES == *"multi"* ]]; then
	if [ $CORAL == 0 ]; then
		python -m tfliteserve -m tflite_2023/ssd_multi.tflite -l tflite_2023/multi.txt -j -1 -T detector
	else
		python -m tfliteserve -m tflite_2023/ssd_multi_edge.tflite -l tflite_2023/multi.txt -e -j -1 -T detector
	fi
else
	if [ $CORAL == 0 ]; then
		python -m tfliteserve -m autopolls_od_v11_2026/yolov11n_beedetector.tflite -l autopolls_od_v11_2026/labels.txt -j -1 -T detector
	else
		python -m tfliteserve -m autopolls_od_v11_2026/yolov11n_beedetector.tflite -l autopolls_od_v11_2026/labels.txt -e -j -1 -T detector
	fi
fi
