# Autopolls installation

**Welcome to the AutoPollS Github!** For more updates and detailed instructions check out the [AutoPollS](https://www.autopolls.ai) website.

### Tested configuration (May 2026)

* Raspberry Pi 4 Model B Rev 1.5 (2 GB)
* Raspberry Pi OS 64-bit, released 2026-04-01 (Raspberry Pi Imager)
* Raspbian GNU/Linux 12 (bookworm) / Debian 13.4
* Kernel: Linux 6.12.75+rpt-rpi-v8 aarch64

---

# Install OS

Install the latest Pi OS using Raspberry Pi Imager before proceeding. 

# Environment variables

Several environment variables are required to access the AutoPollS UI. Add the following lines to the **top** of your `~/.bashrc` (before the `if not running interactively` block). Change the values to your choice of username and password:

```bash
sudo nano ~/.bashrc
```

```bash
export PCAM_USER="camera login user name"
export PCAM_PASSWORD="camera login password"
```

Save and exit with `Ctrl+X`, then `Y`.

# Clone this repository

```bash
. ~/.bashrc
cd
git clone https://github.com/Crall-Lab/Autopolls.git
```

*Note: select `y` if prompted to continue.*

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

# Install pandas and libsystemd

```bash
pip install pandas ai_edge_litert
sudo apt install libsystemd-dev
```

# Install tfliteserve

```bash
cd ~/Autopolls/tfliteserve

# Latest installs may require a pinned setuptools version
pip3 install setuptools

# Install Edge TPU support

# Install the tfliteserve package
pip3 install -e .
```

# Install the pcam (Autopolls) package

```bash
cd ~/Autopolls/pcam
pip install -e .
pip install uwsgi
```

# Copy default config to Desktop

```bash
sudo cp ~/Autopolls/utils/configs ~/Desktop/configs
sudo chmod 777 ~/Desktop/configs
```

To edit config values, use the included GUI editor:
```bash
python3 ~/Autopolls/utils/config_editor.py
```

# Setup storage location

You will need a properly formatted external hard drive. The instructions below format the drive directly on the Pi — **this will erase all existing data on the drive**. If your drive is already formatted, skip to the "Mount storage location" section.

1. Connect your external USB hard drive to the Pi.
2. The software assumes the drive is at `/dev/sda1`. Confirm with:
```bash
sudo fdisk -l
```
3. Unmount and reformat as NTFS (supports >2 TB volumes):
```bash
sudo umount /dev/sda1
sudo fdisk /dev/sda
```

Inside `fdisk`, run these commands in order:
- `g` — switch to GPT
- `d` — delete existing partitions (if any)
- `n` — create a new partition (press Enter three times to accept all defaults)
- `t` then `11` — set partition type to Microsoft Basic Data
- `w` — write changes and exit

4. Create the NTFS filesystem:
```bash
sudo mkfs.ntfs -f /dev/sda1
```

## Mount storage location

```bash
echo "/dev/sda1 /mnt/data auto defaults,nofail,user,uid=1000,gid=124,umask=002  0 0" | sudo tee -a /etc/fstab
sudo mkdir /mnt/data
sudo mount /mnt/data
sudo mkdir -p /mnt/data/logs
sudo chown $USER /mnt/data
sudo chgrp ftp /mnt/data
sudo chmod 775 /mnt/data
```

## Change hostname file permissions

```bash
sudo chmod 777 /etc/hostname
```

# Setup web server (for UI)

```bash
sudo htpasswd -bc /etc/apache2/.htpasswd pcam $PCAM_PASSWORD
sudo rm /etc/nginx/sites-enabled/default
sudo ln -s ~/Autopolls/services/pcam-ui.nginx /etc/nginx/sites-enabled/
```

# Setup systemd services

Run the configuration script to set the correct username in all service files:

```bash
bash ~/Autopolls/pcam/services/configure_services.sh
```

Then symlink the services into systemd, enable them on boot, and start them:

```bash
cd ~/Autopolls/pcam/services
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-overview.service \
    pcam-overview.timer \
    pcam@.service \
    pcam-ui.service; do \
  sudo ln -s ~/Autopolls/pcam/services/$S /etc/systemd/system/$S
done

# Enable services to run on boot
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-overview.timer \
    pcam-ui.service; do \
  sudo systemctl enable $S
done

# Start services
for S in \
    tfliteserve.service \
    pcam-discover.service \
    pcam-ui.service; do \
  sudo systemctl start $S
done

sudo systemctl restart nginx
```

*Note: the overview service and timer are not needed for USB cameras and may be removed in a future update.*

# Remove Admin Permissions for SystemD control from boot
As of May 2026, the Pi OS requires admin password for SystemD control of executables. To allow systemD control off boot
these permissions must be disabled. To do this:
1. Within the Pi GUI, click on the start menu (top left of screen)
2. Select the "Preferences" tab
3. Then select the 'Control Centre" tab
4. Toggle "Admin Password" to "off" by clicking



# Add script to fix and remount /dev/sda1 if corrupted

NTFS corruption can occur after extended use. The following cron job monitors and repairs the mount automatically.

#Open crontab (`crontab -e`) and add this line:

#```
#* * * * * sudo python3 ~/Autopolls/utils/mountFix.py
#```

# Install MCC134 libraries and script (optional)


Attach the MCC134 thermocouple board to the Pi's 40-pin GPIO, then run:

```bash
cd ~
#sudo apt-get install libraspberrypi-dev raspberrypi-kernel-headers
git clone https://github.com/mccdaq/daqhats.git
cd ~/daqhats
#~/.virtualenvs/autopolls/bin/pip install daqhats
sudo ./install.sh
```

If the libraries do not install automatically:

```bash
#deactivate
#sudo pip install daqhats --break-system-packages
```

Move the temperature sensor script into the daqhats example directory:

```bash
sudo chmod 775 ~/Autopolls/utils/tempSensor.py
sudo mv ~/Autopolls/utils/tempSensor.py ~/daqhats/examples/python/mcc134/tempSensor.py
```

Open crontab (`crontab -e`) and add this line:

```
* * * * * sudo python3 ~/daqhats/examples/python/mcc134/tempSensor.py
```

Reboot, then confirm readings are being recorded:

```bash
sudo reboot -h now
# After reboot:
sudo python3 ~/daqhats/examples/python/mcc134/tempSensor.py
```

A folder `/mnt/data/tempProbes` should appear containing a CSV with hostname and temperature readings.

# Install wittyPi libraries and script (optional)

Attach the wittyPi on top of the thermocouple board's 40-pin GPIO. If using an older wittyPi, replace `WittyPi4` with `WittyPi3`.

```bash
wget http://www.uugear.com/repo/WittyPi4/install.sh
sudo sh install.sh
```

Reboot, then activate the schedule:

```bash
sudo mv ~/Autopolls/utils/schedule.wpi ~/wittypi/schedule.wpi
sudo ~/wittypi/runScript.sh
```

# Viewing cameras — option 1: preview script

To preview attached cameras and check orientation and focus, run:

```bash
python3 ~/Autopolls/utils/pcamPreview.py -t 30
```

This shows a 30-second preview. Adjust `-t` to change the duration. Use `-f <value>` to test a specific focal distance; if omitted, the value from `~/Desktop/configs` is used.

# Viewing cameras — option 2: web UI

Open a browser on the Pi and navigate to `127.0.0.1`. Log in with the credentials set in `PCAM_USER` / `PCAM_PASSWORD`. This provides an overview of recent detections (not a real-time camera feed).

# Troubleshooting

### systemd errors
```bash
pip3 install systemd
```

### Check service status
```bash
# Check that the model loaded and is running
sudo systemctl status tfliteserve.service

# Check a specific camera (press Tab to autocomplete the IP)
sudo systemctl status pcam@

# View logs for a service
sudo journalctl -au pcam-discover
```
