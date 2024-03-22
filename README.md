Installation notes
-----

# Install OS

Install latest Pi OS (tested March 17th, 2024)

Test conditions:
* Raspberry Pi 4 Model B Rev 1.5 [ 2GB ]
* Raspberry Pi OS (64-bit, released 2024-03-15) - from raspberry pi imager
* Raspbian GNU/Linux 12 (bookworm)
* Debian version: 12.0
* Kernel version: Linux 6.6.20+rpt-rpi-v8 aarch64

Setup locale, timezone, keyboard, hostname, ssh

# Environment variables

Several environment variable are used for configuration/running. To accesss the AutoPollS UI, you will need to set up a custom user and password, which you will do in the bashrc script. Open Terminal  on your pi and run the following command:

```bash
sudo nano ~/.bashrc
```
This will open the bashrc file in the nano text editor. Now add the lines to the bashrc script. NB: these must be at the TOP of your bashrc (before the 'If not running interactively'... line). 
```bash
export PCAM_USER="camera login user name"
export PCAM_PASSWORD="camera login password"
```
After you have added these lines at the top of your bashrc script, you can save and exit by pressing CTRL+X, then selecting 'Y' (yes) when asked if you want to save the modified buffer. You will be prompted to do both of these steps in the nano editor.

# Clone this repository

Prepare for and clone this repository
```bash
. ~/.bashrc
mkdir -p ~/AP
cd ~/AP
git clone https://github.com/Crall-Lab/Autopolls.git
```
*NB select 'y' if prompted whether you want to continue...

# Install pre-requisites

```bash
sudo apt update
sudo apt install python3-numpy python3-opencv python3-requests python3-flask python3-systemd nginx-full vsftpd virtualenvwrapper apache2-utils python3-gst-1.0 gstreamer1.0-tools nmap
echo "source /usr/share/virtualenvwrapper/virtualenvwrapper.sh" >> ~/.bashrc
```

# Setup virtualenv

```bash
. ~/.bashrc
mkvirtualenv --system-site-packages autopolls -p `which python3`
workon autopolls
echo "source ~/.virtualenvs/autopolls/bin/activate" >> ~/.bashrc
```
# Install pandas for CSV export support

```bash
pip install pandas
```
# Install tfliteserve

```bash
mkdir -p ~/AP
cd ~/AP
git clone https://github.com/braingram/tfliteserve.git
cd tfliteserve

# Latest installs have required previous setuptools version
pip3 install setuptools==65.7.0

# the following tflite runtime installation instructions are from here: https://www.tensorflow.org/lite/guide/python

# install edge support
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update
#sudo apt install python3-tflite-runtime
pip install tflite-runtime==2.14.0
sudo apt-get install libedgetpu1-std

pip3 install -e .
# get model (TODO 404 permission denied, host this in repo or publicly)
wget https://github.com/braingram/tfliteserve/releases/download/v0.1/200123_2035_model.tar.xz
tar xvJf 200123_2035_model.tar.xz
```

# Install this repository

```bash
cd ~/AP/Autopolls
pip install -e .
pip install uwsgi
```
Move latest object detection model to tfliteserve folder
```bash
sudo cp /home/pi/AP/Autopolls/tflite_20220630_1/ /home/pi/AP/tfliteserve/tflite_20220630_1 -r
sudo mkdir /home/pi/AP/tfliteserve/tflite_2023/
sudo cp /home/pi/AP/Autopolls/testModels/ssd_mobilenetV2_fpnlite_UINT8_AP24.tflite /home/pi/AP/tfliteserve/tflite_2023/ssd_single.tflite
sudo cp /home/pi/AP/Autopolls/testModels/ssd_mobilenetV2_fpnlite_UINT8_AP24_edgetpu.tflite /home/pi/AP/tfliteserve/tflite_2023/ssd_single_edge.tflite
sudo cp /home/pi/AP/Autopolls/testModels/ssd_mobilenetV2_fpnlite_UINT8_AP26.tflite /home/pi/AP/tfliteserve/tflite_2023/ssd_multi.tflite
sudo cp /home/pi/AP/Autopolls/testModels/ssd_mobilenetV2_fpnlite_UINT8_AP26_edgetpu.tflite /home/pi/AP/tfliteserve/tflite_2023/ssd_multi_edge.tflite
sudo cp /home/pi/AP/Autopolls/testModels/ssd_mobilenetV2_fpnlite_UINT8_AP26_edgetpu.tflite /home/pi/AP/tfliteserve/tflite_2023/ssd_multi_edge.tflite
sudo cp /home/pi/AP/Autopolls/testModels/ssd_mobilenetV2_fpnlite.txt /home/pi/AP/tfliteserve/tflite_2023/multi.txt
sudo cp /home/pi/AP/Autopolls/tflite_20220630_1/labels.txt /home/pi/AP/tfliteserve/tflite_2023/single.txt
sudo cp /home/pi/AP/Autopolls/configs /home/pi/Desktop/configs
sudo cp /home/pi/AP/Autopolls/pcamPreview.py /home/pi/pcamPreview.py
sudo chmod 777 /home/pi/Desktop/configs
sudo chmod 777 /home/pi/AP/tfliteserve/tflite_2023/
```
Install json reading package
```bash
sudo apt-get install jq
```

# Setup storage location
You will need a properly formatted external hard drive. These instructions will help you format your hard drive directly on the pi, but only need to be run once (i.e., if your hard drive has been previously formatted, you can skip this section). **NB this will delete all existing data on your hard drive** 
1. Connect your external USB hard drive to the pi.
2. The software assumes you're using an external storage drive that is initally mounted at /dev/sda1. To confirm this, check the thumbdrive mounting location using - "sudo fdisk -l" in Terminal. You should see '/dev/sda1' the 'Device' output.
3. To format the drive as ntfs (the most tested format for AutoPollS, and which allows for >2TB volumes), first open 'fdisk' in Terminal using the following command:
```bash
sudo fdisk /dev/sda
```
4. Type 'g': this will switch to gpt
5. Type 'd': this will delete existing partitions, if any
6. Type 'n': this makes a new partion that takes up all disk space. **NB use all defaults** for partition number, first sector, and last sector (i.e., hit 'enter' three time)
7. Type 't' then  '11' when prompted for partition type: this will switch the partion type to microsoft basic data
8. Type 'w': this writes the changes through fdisk
9. Run the following command in Terminal to make the filesystem:
```bash
# make ntfs filesystem
sudo mkfs.ntfs -f /dev/sda1
```

Mount storage location
```bash
echo "/dev/sda1 /mnt/data auto defaults,nofail,user,uid=1000,gid=124,umask=002  0 0" | sudo tee -a /etc/fstab
sudo mkdir /mnt/data
sudo mount /mnt/data
sudo mkdir -p /mnt/data/logs
sudo chown pi /mnt/data
sudo chgrp ftp /mnt/data
sudo chmod 775 /mnt/data
```

Change hostname file permissions
```bash
sudo chmod 777 /etc/hostname
```

# Setup web server (for UI)
```bash
sudo htpasswd -bc /etc/apache2/.htpasswd pcam $PCAM_PASSWORD
sudo rm /etc/nginx/sites-enabled/default
sudo ln -s /home/pi/AP/Autopolls/services/pcam-ui.nginx /etc/nginx/sites-enabled/
```

# Setup systemd services
This will set up the systemd services to run the AutoPollS software in the background. NB: the overview service and timer are not needed for usb cameras, and may be removed in a future update

```bash
cd ~/AP/Autopolls/services
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-overview.service \
    pcam-overview.timer \
    pcam@.service \
    pcam-ui.service; do \
  sudo ln -s ~/AP/Autopolls/services/$S /etc/systemd/system/$S
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
sudo apt-get install libraspberrypi-dev raspberrypi-kernel-headers
```
```bash
cd ~
git clone https://github.com/mccdaq/daqhats.git
cd ~/daqhats
sudo ./install.sh
```
```bash
sudo chmod 775 ~/AP/Autopolls/tempSensor.py
sudo mv ~/AP/Autopolls/tempSensor.py ~/daqhats/examples/python/mcc134/tempSensor.py
```
Open crontab and add this line
```bash
* * * * * sudo python3 ~/daqhats/examples/python/mcc134/tempSensor.py
```
Test that the temperature probes are reading correctly. First, reboot the pi, which you can do with the following command:
```bash
sudo reboot -h now
```

```bash
sudo python ~/daqhats/examples/python/mcc134/tempSensor.py
```
Then confirm a folder in /mnt/data titled "tempProbes", which should contain csv with a temp reading recorded into a csv file. The csv file should contain the hostname and date.

# Install wittyPi libraries and script

Attach the wittyPi on top of the thermocouples 40 pin GPIO, then run commands below. If using an old wittyPi replace with "WittyPi3"
```bash
wget http://www.uugear.com/repo/WittyPi4/install.sh
sudo sh install.sh
```
```bash
sudo mv ~/AP/Autopolls/schedule.wpi ~/wittypi/schedule.wpi
sudo ./wittypi/runScript.sh
```
# Check camera acquisition parameters (optional)

```bash
v4l2-ctl -l
```
```bash
v4l2-ctl -d 0 -c exposure_auto=1 -c exposure_absolute=133 #example of editing acquisition from command line, disable auto-exposure
```
```bash
sudo apt install guvcview uvcdynctrl
```
```bash
sudo systemctl stop pcam@ #hit tab to autocomplete for the connected cameras
```
```bash
guvcview
```

# Viewing camera
In the browser on the pi, you can view attached cameras and change parameters by connecting to the UI: open a browser, and type in "127.0.0.1"

# If errors with systemD
```bash
pip3 install systemd
```

# troubleshooting commands via systemctl
```bash
# check that model is loaded and executed correctly
sudo systemctl status tfliteserve.service
```

```bash
# check that each camera is running correctly, hit tab to complete command for each camera
sudo systemctl status pcam@
```
