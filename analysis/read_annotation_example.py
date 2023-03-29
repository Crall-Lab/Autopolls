"""
The timelapse image annotations are stored in a sqlite database (pcam_210625.sqlite
is most current as of Sept 2021).

Sqlite databases contain one or more tables (sort of like sheets in a spreadsheet).

The columns below are listed in a order that is easy to understand when read and NOT
necessarily the same order as the columns in the table (the first column described is
not necessarily column 1).

There are a few tables that were generated when the raw data was 'indexed':
    - cameras: camera information table
        - camera_id: unique number for each camera
        - mac: mac address
        - module: the module (1-4) to which the camera belonged
        - location: the grid location where the camera was installed
        - start: the first day when the camera data was valid
        - end: the last day when the camera data was valid
    - configs: table of system config changes
        - config_id: unique number for each config file
        - camera_id: corresponding camera id (see above)
        - timestamp: datetime when the config was changed
        - path: file path where the config file is located (relative, starts with Module[1-4]
    - detections: table of detection event files
        - detection_id: unique number for each detection event file
        - camera_id: corresponding camera id
        - timestamp: datetime when event occurred
        - path: relative path to event file
    - stills: table of timelapse/still image files
        - still_id: unique number for each image
        - camera_id: corresponding camera id
        - timestamp: datetime when image was taken
        - path: relative path to image
    - videos: table of video files
        - video_id: unique number for each video
        - camera_id: corresponding camera id
        - timestamp: datetime when the video was recorded
        - path: relative path to video

and some tables added to store annotations:
including some that are used to encode common strings (bbox, tag and label names)
    - bbox_labels: table with code to bbox name
        - bbox_label_id: unique bbox name/label code
        - name: corresponding string for the code
    - label_names: table with code to label name
        - label_id: unique label name code
        - name: corresponding string for the code
    - tag_names: table with code to tag name
        - tag_id: unique tag name code
        - name: corresponding string for the code

and finally the annotations:
    - bboxes: bounding box table
        - bbox_id: unique number for each bbox
        - still_id: corresponding still id
        - label_id: corresponding bbox_label_id (note the name difference: see bbox_labels)
        - left: left pixel coordinate of bounding box
        - right: right pixel coordinate
        - top: top pixel coordinate
        - bottom: bottom pixel coordinate
    - labels: label (annotations for single points) table
        - annotation_id: unique number for each label
        - label_id: corresponding label_id (see label_names) 
        - still_id: corresponding still id
        - x: label x pixel coordinate
        - y: label y pixel coordinate
    - tags: tag (annotations for an entire image) table
        - annotation_id: unique number for each tag
        - tag_id: corresponding tag_id (see tag_names)
        - still_id: corresponding still id
"""

import datetime
import sqlite3


fn = 'pcam_210625.sqlite'

# open the database and auto-detect some datatypes (like timestamps)
db = sqlite3.connect(fn, detect_types=sqlite3.PARSE_DECLTYPES)

# fetch all table names (sqlite returns rows as lists so get the 1st column of each)
table_names = [
    row[0] for row in
    db.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
print(f"Database in {fn} contains {len(table_names)} tables with names:")
for name in sorted(table_names):
    print(f"\t{name}")

# the simpliest way to work with the tables is to fetch all their data (when it's small)
cameras = db.execute("SELECT * FROM cameras").fetchall()

# the 'cameras' table contains information about the cameras
# 'execute' returns a 'cursor' that can be used to fetch data and contains
# a description of the data
cursor = db.execute("SELECT * FROM cameras")
col_names = [row[0] for row in cursor.description]
print("The camera table contains columns:")
for (i, name) in enumerate(col_names):
    print(f"\t{i}: {name}")

# the cursor can be used to fetch all the data
camera_info = cursor.fetchall()
print(f" and {len(camera_info)} rows")

# find a specific camera
camera_row = [row for row in camera_info if row[1] == '001f543e36f9']
print("Info for 1 camera:")
for (i, col) in enumerate(camera_row):
    print(f"\t{i}[{col_names[i]}] = {col}")

# or find it using sqlite
matching_rows = db.execute("SELECT * FROM cameras WHERE mac='001f543e36f9'").fetchall()
if len(matching_rows) != 1:
    raise Exception(f"Failed to find 001f543e36f9 info (found {len(matching_rows)} rows)")
camera_row = matching_rows[0]

# even better, limit the search to 1 result, only fetch 1 row
camera_row = db.execute("SELECT * FROM cameras WHERE mac='001f543e36f9' LIMIT 1").fetchone()

# using this camera id let's find information about a specifc period of time
# 2020-08-29 around 06:08:54
camera_id = camera_row[0]

# find all still_ids for that day
start = datetime.datetime.strptime('2020-08-29 00:00:00', '%Y-%m-%d %H:%M:%S')
end = start + datetime.timedelta(days=1)
# select only the still_id column from each row in the stills table where
# the camera_id matches the provided number and the timestamp is between start and end
still_ids = [
        row[0] for row in db.execute(
            "SELECT still_id FROM stills WHERE camera_id=? AND timestamp>=? AND timestamp<?",
            (camera_id, start, end))]
# The above formatting looks a bit odd as sqlite likes to handle it's own
# string formatting. This is to try and avoid sql injections so it's a good idea
# to let it do it's thing: https://xkcd.com/327/

print(f"Found {len(still_ids)} still images for camera {camera_id} between {start} and {end}")

# next lets find any annotations (bboxes, labels, tags) for these images
# one way to do this would be to iterate through the 1440 still ids and check each of the 3
# tables for each id (so 1440 * 3 = 4320 queries).
# Alternatively, we could leverage sql to select for us in 3 queries
tags = db.execute(
    """
    SELECT * FROM tags
        WHERE still_id IN (
            SELECT still_id FROM stills
                WHERE camera_id=? AND timestamp>=? AND timestamp<?)
    """, (camera_id, start, end)).fetchall()
labels = db.execute(
    """
    SELECT * FROM labels
        WHERE still_id IN (
            SELECT still_id FROM stills
                WHERE camera_id=? AND timestamp>=? AND timestamp<?)
    """, (camera_id, start, end)).fetchall()
bboxes = db.execute(
    """
    SELECT * FROM bboxes
        WHERE still_id IN (
            SELECT still_id FROM stills
                WHERE camera_id=? AND timestamp>=? AND timestamp<?)
    """, (camera_id, start, end)).fetchall()
print(f"Found {len(tags)} tags")
print(f"Found {len(labels)} labels")
print(f"Found {len(bboxes)} bboxes")

# Now get and print out information for each annotation.
# Before we do that, let's fetch some information about how the annotations are encoded.
# Rather than store the full name for each annotation names are encoded in a separate
# table and the code (a unique number for each name) is stored with each annotation

# this creates a dictionary with tag codes as keys and names as values to allow easy lookup
# of a tag name given a tag code
tag_code_to_name = {row[0]: row[1] for row in db.execute('SELECT * FROM tag_names')}
label_code_to_name = {row[0]: row[1] for row in db.execute('SELECT * FROM label_names')}
bbox_code_to_name = {row[0]: row[1] for row in db.execute('SELECT * FROM bbox_labels')}

print("Tags:")
for tag in tags:
    annotation_id, still_id, tag_id = tag
    name = tag_code_to_name[tag_id]
    print(f"\tImage {still_id} has tag {name}[{tag_id}]")
    if name in ('start', 'end'):
        # find timestamp for the corresponding still image
        timestamp = db.execute(
            'SELECT timestamp FROM stills WHERE still_id=?', (still_id, )).fetchone()[0]
        print(f"\t\t{name} tag at {timestamp}")

print("Labels:")
for label in labels:
    annotation_id, still_id, label_id, x, y = label
    name = label_code_to_name[label_id]
    print(f"\tImage {still_id} has label {name}[{label_id}] at pixel ({x}, {y})")

print("Bounding boxes:")
for bbox in bboxes:
    bbox_id, still_id, label_id, left, top, right, bottom = bbox
    name = bbox_code_to_name[label_id]
    print(f"\tImage {still_id} has bbox for {name}[{bbox_id}] at ({top}, {left}, {right}, {bottom})")
