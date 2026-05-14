# Autopolls installation

### Tested configuration (May 2026)

* Raspberry Pi 4 Model B Rev 1.5 (2 GB)
* Raspberry Pi OS 64-bit, released 2026-04-01 (Raspberry Pi Imager)
* Raspbian GNU/Linux 12 (bookworm) / Debian 13.4
* Kernel: Linux 6.12.75+rpt-rpi-v8 aarch64

---

# Install OS

Install the latest Pi OS using Raspberry Pi Imager. During setup, configure locale, timezone, keyboard, hostname, and SSH.

# Install

## 1. System dependencies 

These packages are not available on PyPI and must be installed via apt:

```bash
sudo apt update
sudo apt install \
  python3-gst-1.0 python3-systemd python3-tflite-runtime \
  libedgetpu1-std libsystemd-dev \
  nginx-full vsftpd \
  virtualenvwrapper apache2-utils \
  nmap jq
```

## 2. Virtualenv

```bash
. ~/.bashrc
mkvirtualenv --system-site-packages autopolls -p `which python3`
echo "source ~/.virtualenvs/autopolls/bin/activate" >> ~/.bashrc
workon autopolls
```

## 3. Clone and pip install

```bash
. ~/.bashrc
cd ~
git clone https://github.com/Crall-Lab/Autopolls.git
cd Autopolls
pip install -e tfliteserve/ -e pcam/ -e .
```

This installs three packages (`tfliteserve`, `pollinatorcam`, `autopolls`) and
registers the following commands in the virtualenv:

| Command | Description |
|---|---|
| `autopolls-install` | System setup (run once with sudo, see below) |
| `autopolls-config` | Open the config file GUI editor |
| `pcam-run <ip>` | Start a camera grabber for a given IP or `/dev/videoX` |
| `pcam-discover` | Scan the network for cameras and start services |
| `tfliteserve-server` | Start the TFLite inference server |

## 4. System setup

Run the installer once to configure service files, set up nginx, and copy the
default config. It requires sudo to write to `/etc/systemd/system/`:

```bash
sudo autopolls-install
```

The installer:
- Checks that all apt dependencies are present
- Prompts for camera username and password, saves to `~/.config/autopolls/credentials` (mode 600)
- Copies the default config to `~/Desktop/configs` (if not already present)
- Writes patched `.service` files to `/etc/systemd/system/` (correct user, paths, and credentials file)
- Enables services to start on boot
- Configures nginx and htpasswd for the web UI

No `~/.bashrc` edits are needed for credentials.

Follow the printed instructions for any remaining manual steps.

## 5. Edit config

```bash
autopolls-config
```

Or edit `~/Desktop/configs` directly (it's a JSON file). Key fields:

| Field | Type | Description |
|---|---|---|
| `hostname` | string | Device hostname (written to `/etc/hostname` on startup) |
| `model_inference` | 0/1 | Enable TFLite detection |
| `classes` | `single`/`multi` | Bee-only or multi-insect model |
| `coral` | 0/1 | Use Coral Edge TPU accelerator |
| `threshold` | 0.0–1.0 | Detection confidence threshold |
| `periodic_still` | int (s) | Save a still image every N seconds |
| `autofocus` | 0/1 | Enable camera autofocus |
| `focus` | 1–999 | Manual focus position (larger = closer) |
| `csv` | 0/1 | Save detections as CSV (vs JSON) |
| `save_all_detections` | 0/1 | Save every detection, not just triggered events |

---

# Setup storage location

You will need a properly formatted external hard drive. The instructions below
format the drive on the Pi — **this will erase all existing data**. If your
drive is already formatted, skip to "Mount storage location".

1. Connect the USB hard drive to the Pi.
2. Confirm the drive is at `/dev/sda1`:
```bash
sudo fdisk -l
```
3. Unmount and reformat as NTFS (supports >2 TB):
```bash
sudo umount /dev/sda1
sudo fdisk /dev/sda
```

Inside `fdisk`, run in order:
- `g` — switch to GPT
- `d` — delete existing partitions (if any)
- `n` — new partition (press Enter three times to accept defaults)
- `t` then `11` — set type to Microsoft Basic Data
- `w` — write and exit

4. Create the filesystem:
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

## Add cron job to repair /dev/sda1 if corrupted

Open crontab (`crontab -e`) and add:

```
* * * * * sudo python3 ~/Autopolls/utils/mountFix.py
```

---

# Install MCC134 thermocouple board (optional)

Attach the MCC134 to the Pi's 40-pin GPIO, then:

```bash
sudo apt-get install libraspberrypi-dev raspberrypi-kernel-headers
git clone https://github.com/mccdaq/daqhats.git ~/daqhats
cd ~/daqhats && sudo ./install.sh
```

If the libraries do not install automatically:

```bash
~/.virtualenvs/autopolls/bin/pip install daqhats
deactivate
sudo pip install daqhats --break-system-packages
```

Move the temperature sensor script and add a cron job:

```bash
sudo chmod 775 ~/Autopolls/utils/tempSensor.py
sudo mv ~/Autopolls/utils/tempSensor.py ~/daqhats/examples/python/mcc134/tempSensor.py
```

Open crontab (`crontab -e`) and add:

```
* * * * * sudo python3 ~/daqhats/examples/python/mcc134/tempSensor.py
```

Reboot and confirm readings appear in `/mnt/data/tempProbes/`.

---

# Install wittyPi power scheduler (optional)

Attach the wittyPi on top of the thermocouple board. Replace `WittyPi4` with
`WittyPi3` if using an older model.

```bash
wget http://www.uugear.com/repo/WittyPi4/install.sh
sudo sh install.sh
```

After rebooting:

```bash
sudo mv ~/Autopolls/utils/schedule.wpi ~/wittypi/schedule.wpi
sudo ~/wittypi/runScript.sh
```

---

# Viewing cameras

## Option 1: preview script

```bash
python3 ~/Autopolls/utils/pcamPreview.py -t 30
```

Shows a 30-second preview. Use `-f <value>` to test a focus distance; if
omitted, the value from `~/Desktop/configs` is used.

## Option 2: web UI

Open `http://127.0.0.1` in the Pi's browser (or `http://<pi-ip>` from another
device on the same network). Log in with the credentials set in `PCAM_USER` /
`PCAM_PASSWORD`.

---

# Troubleshooting

```bash
# Check that the inference server loaded correctly
sudo systemctl status tfliteserve.service

# Check a specific camera (Tab to autocomplete the IP)
sudo systemctl status pcam@

# Stream logs for a service
sudo journalctl -fu pcam-discover

# If systemd Python bindings are missing
pip3 install systemd
```
