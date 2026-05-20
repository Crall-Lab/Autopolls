#!/bin/bash

source $HOME/.bashrc
source $HOME/.virtualenvs/autopolls/bin/activate

cd $HOME/Autopolls/pcam

# exec here to use same PID to allow systemd watchdog
#exec python3 -m pollinatorcam -l $1 -rdD
# TODO flag for usb vs IP camera
MODELSTATUS=`cat $HOME/Desktop/configs | jq '.model_inference'`

if [ $MODELSTATUS == 0 ]
then
	exec python3 -m pollinatorcam -cDfrt -l $1 -v
else
	exec python3 -m pollinatorcam -cDrt -l $1 -v
fi
