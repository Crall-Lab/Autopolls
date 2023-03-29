Installation notes
-----

# Install OS

Install latest Pi OS (Desktop: tested March 2020)
Setup locale, timezone, keyboard, hostname, ssh

# Environment variables

Several environment variable are used for configuration/running. Please set
the following in your ~/.bashrc (or wherever else is appropriate). Note this
must be at the TOP of your bashrc (before the 'If not running interactively'... line).
You may have to use nano in the terminal to make these edits:

TODO make a PCAM_HOME environment variable to make switching forks easier
```bash
sudo nano ~/.bashrc
```

```bash
export PCAM_USER="camera login user name"
export PCAM_PASSWORD="camera login password"
export PCAM_NAS_USER="ftp server user"
export PCAM_NAS_PASSWORD="ftp server password"
```

Update the raspberry pi hostname with a unique ID of your choosing
```bash
sudo nano /etc/hostname
# autopolls have the naming scheme "AP_XX", where XX is a number ie; 05
```

# Clone this repository

Prepare for and clone this repository
```bash
. ~/.bashrc
mkdir -p ~/r/braingram
cd ~/r/braingram
git clone https://github.com/mattsmiths/pollinatorcam.git -b detection_network
```

# Install pre-requisites

```bash
sudo apt update
sudo apt install python3-numpy python3-opencv python3-requests python3-flask python3-systemd nginx-full vsftpd virtualenvwrapper apache2-utils python3-gst-1.0 gstreamer1.0-tools nmap
echo "source /usr/share/virtualenvwrapper/virtualenvwrapper.sh" >> ~/.bashrc
```

# Setup virtualenv

```bash
. ~/.bashrc
mkvirtualenv --system-site-packages pollinatorcam -p `which python3`
workon pollinatorcam
echo "source ~/.virtualenvs/pollinatorcam/bin/activate" >> ~/.bashrc
```

# Install tfliteserve

```bash
mkdir -p ~/r/braingram
cd ~/r/braingram
git clone https://github.com/braingram/tfliteserve.git
cd tfliteserve

# the following tflite runtime installation instructions are from here: https://www.tensorflow.org/lite/guide/python

# install edge support
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update
sudo apt install python3-tflite-runtime
sudo apt-get install libedgetpu1-std

pip3 install -e .
# get model (TODO 404 permission denied, host this in repo or publicly)
wget https://github.com/braingram/tfliteserve/releases/download/v0.1/200123_2035_model.tar.xz
tar xvJf 200123_2035_model.tar.xz
```

# Install this repository

```bash
cd ~/r/braingram/pollinatorcam
pip install -e .
pip install uwsgi
```
Move latest object detection model to tfliteserve folder
```bash
sudo mv ~/r/braingram/pollinatorcam/tflite_20220630_1/ ~/r/braingram/tfliteserve/tflite_20220630_1
```

# Setup storage location

This assumes you're using an external storage drive that shows up as /dev/sda1. One option is to setup the drive as ntfs.
To format the drive as ntfs (to allow for >2TB volumes) in fdisk you will need to:
```bash
# confirm /dev/sda is your external drive before proceeding
# open fdisk
sudo fdisk /dev/sda
# switch to gpt: g
# delete all partions: d (for each partion)
# make a new partion that takes up all disk space: n (use all defaults)
# switch the partion type to microsoft basic data: t 11
# write fdisk: w
# make ntfs filesystem
sudo mkfs.ntfs -f /dev/sda1
```

Mount storage location

```bash
echo "/dev/sda1 /mnt/data auto defaults,user,uid=1000,gid=124,umask=002  0 0" | sudo tee -a /etc/fstab
sudo mkdir /mnt/data
sudo mount /mnt/data
sudo mkdir -p /mnt/data/logs
sudo chown pi /mnt/data
sudo chgrp ftp /mnt/data
sudo chmod 775 /mnt/data
```


# Setup web server (for UI)

```bash
sudo htpasswd -bc /etc/apache2/.htpasswd pcam $PCAM_PASSWORD
sudo rm /etc/nginx/sites-enabled/default
sudo ln -s ~/r/braingram/pollinatorcam/services/pcam-ui.nginx /etc/nginx/sites-enabled/
```

# Setup systemd services

NOTE: the overview service and timer are not needed for usb cameras.

```bash
cd ~/r/braingram/pollinatorcam/services
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-overview.service \
    pcam-overview.timer \
    pcam@.service \
    pcam-ui.service; do \
  sudo ln -s ~/r/braingram/pollinatorcam/services/$S /etc/systemd/system/$S
done
# enable services to run on boot
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-overview.timer \
    pcam-ui.service; do \
  sudo systemctl enable $S
done
# start services
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-ui.service; do \
  sudo systemctl start $S
done
sudo systemctl restart nginx
```

# Install MCC134 libraries and script

Attach the MCC134 thermocouple ontop of the Pi's 40 pin GPIO, then run commands below
```bash
cd ~
git clone https://github.com/mccdaq/daqhats.git
cd ~/daqhats
sudo ./install.sh
```
```bash
sudo chmod 775 ~/r/braingram/pollinatorcam/tempSensor.py
sudo mv ~/r/braingram/pollinatorcam/tempSensor.py ~/daqhats/examples/python/mcc134/tempSensor.py
```
Open crontab and add this line
```bash
* * * * * sudo python3 ~/daqhats/examples/python/mcc134/tempSensor.py
```
Run sudo python ~/daqhats/examples/python/mcc134/tempSensor.py
Confirm a folder in /home/pi/ titled "tempProbes" and a csv with a temp reading is generated

# Install wittyPi libraries and script

Attach the wittyPi on top of the thermocouples 40 pin GPIO, then run commands below
```bash
wget http://www.uugear.com/repo/WittyPi3/install.sh
sudo sh install.sh
```
```bash
sudo mv ~/r/braingram/pollinatorcam/schedule.wpi ~/wittypi/schedule.wpi
sudo ./wittypi/runScript.sh
```

# Configure cameras

In the background, pcam-discover will run network scans to find new cameras.
You can run the following to see what devices were found.

```bash
python3 -m pollinatorcam discover -p
```

When new IP cameras are connected, they will need to be configured. If this is
the first time the camera is configured, you may need to provide a different
username and password (like the default admin/admin).

```bash
# if camera ip is 10.1.1.153
python3 -m pollinatorcam configure -i 10.1.1.153 -u admin -p admin
```

