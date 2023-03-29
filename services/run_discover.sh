#!/bin/bash

source $HOME/.bashrc
source $HOME/.virtualenvs/pollinatorcam/bin/activate

cd $HOME/r/braingram/pollinatorcam

# TODO flag for usb vs IP cameras?
#MY_IP=`ip -o -4 addr list eth0 | awk '{print $4}' | cut -d/ -f1`
#CIDR=$MY_IP/24
#echo "Running discover on network $CIDR"

if [ ! -d "/dev/shm/pcam" ]; then
  mkdir /dev/shm/pcam
  chown pi /dev/shm/pcam
  chgrp pi /dev/shm/pcam
fi
#python3 -m pollinatorcam discover -v -i $MY_IP/24
python3 -m pollinatorcam discover -u
