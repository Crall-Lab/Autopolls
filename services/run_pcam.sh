#!/bin/bash

source $HOME/.bashrc
source $HOME/.virtualenvs/pollinatorcam/bin/activate

cd $HOME/r/braingram/pollinatorcam

# exec here to use same PID to allow systemd watchdog
#exec python3 -m pollinatorcam -l $1 -rdD
# TODO flag for usb vs IP camera
exec python3 -m pollinatorcam -cDrt -l $1 -v
