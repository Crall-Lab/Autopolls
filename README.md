Installation notes
-----

# Install OS

Install latest Pi OS (tested May 12th, 2026)

Test conditions:
* Raspberry Pi 4 Model B Rev 1.5 [ 2GB ]
* Raspberry Pi OS (64-bit, released 2026-04-01) - from raspberry pi imager
* Raspbian GNU/Linux 12 (bookworm)
* Debian version: 13.4
* Kernel version: Linux 6.12.75+rpt-rpi-v8 aarch64

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
cd
git clone https://github.com/Crall-Lab/Autopolls.git
```
*NB select 'y' if prompted whether you want to continue...

# Install pre-requisites
```bash
sudo apt update
sudo apt install python3-numpy python3-opencv python3-requests python3-flask python3-systemd nginx-full vsftpd virtualenvwrapper apache2-utils python3-gst-1.0 gstreamer1.0-tools nmap jq
echo "source /usr/share/virtualenvwrapper/virtualenvwrapper.sh" >> ~/.bashrc
```

# Setup virtualenv

```bash
. ~/.bashrc
mkvirtualenv --system-site-packages autopolls -p `which python3`
workon autopolls
echo "source ~/.virtualenvs/autopolls/bin/activate" >> ~/.bashrc
```
# Install pandas for CSV export support and libssystemd

```bash
pip install pandas
sudo apt install libsystemd-dev
```
# Install tfliteserve

```bash
cd ~/Autopolls/tfliteserve
#git clone https://github.com/braingram/tfliteserve.git

# Latest installs have required previous setuptools version
pip3 install setuptools

# the following tflite runtime installation instructions are from here: https://www.tensorflow.org/lite/guide/python

# install edge support
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update
#sudo apt install python3-tflite-runtime
sudo apt-get install libedgetpu1-std

# Install the tfliteserve package
pip3 install -e .

```

# Install the pcam (Autopolls) repository

```bash
cd ~/Autopolls/pcam
pip install -e .
pip install uwsgi
```

Move util scripts to tfliteserve folder
```bash
sudo cp ~/Autopolls/utils/configs ~/Desktop/configs
sudo chmod 777 ~/Desktop/configs
```

# Setup storage location
You will need a properly formatted external hard drive. These instructions will help you format your hard drive directly on the pi, but only need to be run once (i.e., if your hard drive has been previously formatted, you can skip this section). **NB this will delete all existing data on your hard drive** 
1. Connect your external USB hard drive to the pi.
2. The software assumes you're using an external storage drive that is initally mounted at /dev/sda1. To confirm this, check the thumbdrive mounting location using - "sudo fdisk -l" in Terminal. You should see '/dev/sda1' the 'Device' output.
```bash
sudo umount /dev/sda1
```
3. To format the drive as ntfs (the most tested format for AutoPollS, and which allows for >2TB volumes), first open 'fdisk' in Terminal using the following command:
```bash
sudo fdisk /dev/sda
```
# Proceeding will erase all data and reformat inserted drive in /dev/sda
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
sudo ln -s ~Autopolls/services/pcam-ui.nginx /etc/nginx/sites-enabled/
```

# Setup systemd services
This will set up the systemd services to run the AutoPollS software in the background. NB: the overview service and timer are not needed for usb cameras, and may be removed in a future update

```bash
cd ~/Autopolls/services
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-overview.service \
    pcam-overview.timer \
    pcam@.service \
    pcam-ui.service; do \
  sudo ln -s ~/Autopolls/services/$S /etc/systemd/system/$S
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

# Add script to fix and remount /dev/sda1 if corrupted
We find that there is some fairly frequent ntfs corruption of the mounted drives when plugged in the Autopolls system and running over long periods.
The following scripts should look for this file error and fix it.

In terminal open crontab, via "crontab -e", at the bottom of the file include:
```
* * * * * sudo python3 ~/AP/Autopolls/mountFix.py
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
If libraries do not install automatically
```sh
~/.virtualenvs/autopolls/bin/pip install daqhats
deactivate
sudo pip install daqhats --break-system-packages
```

```bash
sudo chmod 775 ~/Autopolls/tempSensor.py
sudo mv ~/Autopolls/tempSensor.py ~/daqhats/examples/python/mcc134/tempSensor.py
```
Open crontab ('crontab -e' in Terminal) and add this line to the bottom of the script:

```bash
crontab -e
```

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

Reboot your pi again (manually, or using 'sudo reboot -h now'), then run the following command in Terminal:
```bash
sudo mv ~/Autopolls/schedule.wpi ~/wittypi/schedule.wpi
sudo ~/wittypi/runScript.sh
```
# Viewing cameras option 1: camera view and focus
To view the four cameras and check orientation and focus, run the following command in terminal:
```bash
python ~/Autopolls/pcamPreview.py -t 30
```
This will give you a (30-second) preview of the cameras you have attached. You can adjust the '-t' parameters to change the length of the preview. To test focal distance values, you can use the optional -f input value. If not value for -f is input, the script will default to pulling the focal distance specified in the config file on the Desktop.



# Viewing camera option 2: web browser
In the browser on the pi, you can view attached cameras and change parameters by connecting to the UI: open a browser, and type in "127.0.0.1". FYI, you will have to enter. This provide an overview of recent detections, but does not provide a realtime view of the cameras

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
