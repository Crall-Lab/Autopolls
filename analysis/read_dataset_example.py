"""
The data collected during summer/fall 2020 consists of 2 main categories:
    - realtime detection results and triggered videos
    - timelapse images taken 1/min

Subsequent annotations were added to the timelapse images and are stored in a
sqlite database (pcam_210625.sqlite is most current as of Sept 2021).

This gives 2 main repositories of data:
    - raw harddrive (containing realtime and timelapse data)
    - sqlite (containing annotations for timelapse data)


The raw data is organized in a file heirarchy:
    - Module[1-4]: 1 for each 15x camera lorex system + pi
        - <mac address>: named by camera mac address, contains timelapse images
            - <YYYY-MM-DD>/pic_001: subfolder for each day
                - <HH.MM.SS>[R][0@0][0].jpg: timestamped timelapse image
        - configs: camera config changes, a file is generated for each config change
            - <mac address>: camera mac address
                - <YYMMDD_HHMMSS_ffffff>: timestamped config (f.. = partial second)
        - detections:
            - <mac address>: camera mac address
                - <YYMMDD>: detection day
                    - <HHMMSS_ffffff_mac>.json: timestamped detection event details
        - logs:
            - <ip address>.err/out: most recent log files for detection process
        - overviews:
            - <mac address>: camera mac address
                - <mac_YYYY-MM-DD>.mp4: downscaled video of timelapse images for 1 day
        - videos:
            - <mac address>: camera mac address
                - <YYMMDD>: detection day
                     - <HHMMSS_ffffff_mac>.mp4: video of detected event
"""

# import some libraries useful for file paths
import glob
import os


# change to the directory on your computer containing the Module[1-4] subdirectories
data_dir = '/media/graham/377CDC5E2ECAB822/'

# make above path absolute (and expand in case above contains '~')
data_dir = os.path.abspath(os.path.expanduser(data_dir))

# check directory exists
if not os.path.exists(data_dir):
    raise Exception(f"data_dir[{data_dir}] does not exist")

# check that the folder contains 4 modules
sdirs = glob.glob(os.path.join(data_dir, 'Module*'))
if len(sdirs) != 4:
    raise Exception(f"data_dir[{data_dir}] missing Module[1-4] subdirectories")

# load an example detection event
detection_fn = os.path.join(
    data_dir,
    'Module1/detections/001f543e36f9/200829/060854_390877_001f543e36f9.json')

# import module for loading/saving json data
import json

# open the file for 'r'eading and store it in variable f
with open(detection_fn, 'r') as f:
    # load it as json data
    detection_event = json.load(f)
print(f"Detection event read from {detection_fn}")

# the detection event contains information about the current ('meta') and
# previous detection states ('last_meta')
print("Date and time of detection: " + str(detection_event['meta']['datetime']))

# including camera name
print("Camera name: " + str(detection_event['meta']['camera_name']))

# the configured roi (where the detections were made in the low res 640x480 stream)
print("Image rois: " + str(detection_event['meta']['rois']))

# the classes detected and classifier result
print("Detections: " + str(detection_event['meta']['detections']))

# the state of the detector configuration
print("Detector config:")
print("\t" + str(detection_event['meta']['config']))

# the trigger state (events are saved for rising edges, falling edges and timeouts)
print("Trigger state: " + str(detection_event['meta']['state']))

# if this event started a video it will be listed here
video_fn = detection_event['meta'].get('filename', None)
if video_fn is None:
    print("No video file was started for this event")
else:
    # this path is absolute at the time of creation and will start with
    # /mnt/data/videos
    # so strip this original prefix and add our new prefix
    video_fn = os.path.join(
        data_dir,
        'Module1/videos/',
        os.path.relpath(video_fn, '/mnt/data/videos/'))
    if not os.path.exists(video_fn):
        raise IOError(f"Failed to find detection video: {video_fn}")
    print(f"Video started by event: {video_fn}")
