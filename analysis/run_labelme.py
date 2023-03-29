"""
Run select on sqlite3 database to get images (and annotations) to annotate
Symlink images to temporary folder
Run labelme to annotate images
Parse labelme annotations
Save annotations to database

run_labelme.py
  -c <camera_id>
  -d <date as YYMMDD>
  -f <first hour> -l <last hour>
  -s <data source/directory>
  -D <database file path>

cmd args take precedence

if cmd args are not there check env variables
PCAM_LM_CAMERA_ID
PCAM_LM_DATE
PCAM_LM_FIRST_HOUR
PCAM_LM_LAST_HOUR
PCAM_LM_DATA_DIR
PCAM_LM_DATABASE_FILENAME

finally use defaults

if a day successfully finishes, increment the day and save to env
"""

import argparse
import copy
import datetime
import glob
import json
import logging
import math
import os
import sqlite3
import subprocess


options = [
    ('camera_id', 'c', '10'),
    ('date', 'd', '200923'),
    ('first_hour', 'f', 5),
    ('last_hour', 'l', 20),
    ('data_dir', 'D', '/media/graham/377CDC5E2ECAB822'),
    ('database_filename', 'b', 'pcam.sqlite'),
    ('tmp_dir', 't', 'tmp'),
]

cfg_fn = os.path.expanduser('~/.pcam_run_labelme.json')
if os.path.exists(cfg_fn):
    with open(cfg_fn, 'r') as f:
        cfg = json.load(f)
else:
    cfg = {}

parser = argparse.ArgumentParser()
for option in options:
    name, short_name, default = option
    parser.add_argument(
        f'-{short_name}', f'--{name}',
        default=cfg.get(name, default), type=type(default))

parser.add_argument(
    '-v', '--verbose', default=False, action='store_true')
parser.add_argument(
    '-r', '--resume', default=False, action='store_true',
    help="Resume from a previous (crashed) annotation")
parser.add_argument(
    '-s', '--start_end_limit', default=False, action='store_true',
    help="Limit images to those between start and end tags")

args = parser.parse_args()
if args.verbose:
    logging.basicConfig(level=logging.DEBUG)
logging.info(f"Running with options: {vars(args)}")

day = datetime.datetime.strptime(args.date, '%y%m%d')
min_time = day + datetime.timedelta(hours=args.first_hour)
max_time = day + datetime.timedelta(hours=args.last_hour)

db = sqlite3.connect(args.database_filename, detect_types=sqlite3.PARSE_DECLTYPES)


def table_exists(db, table_name):
    res = db.execute("SELECT name from sqlite_master WHERE type='table';")
    for r in res:
        if r[0] == table_name:
            return True
    return False

# open database
# check if tables exist, if not create
# - tag_names: (tag id[int], tag name[str])
if not table_exists(db, 'tag_names'):
    logging.info("database missing tag_names table, adding...")
    db.execute(
        "CREATE TABLE tag_names ("
        "tag_id INTEGER PRIMARY KEY,"
        "name TEXT"
        ");")
    for tag in ('note', 'start', 'end'):
        db.execute(
            "INSERT INTO tag_names (name) VALUES (?);",
            (tag, ))
    db.commit()
# - label_names: (label id[int], label name[str])
if not table_exists(db, 'label_names'):
    logging.info("database missing label_names table, adding...")
    db.execute(
        "CREATE TABLE label_names ("
        "label_id INTEGER PRIMARY KEY,"
        "name TEXT"
        ");")
    for label in ('note', 'flower', 'pollinator'):
        db.execute(
            "INSERT INTO label_names (name) VALUES (?);",
            (label, ))
    db.commit()
# - tags: (still id[int], tag id[int])  # can be multiple per image
if not table_exists(db, 'tags'):
    logging.info("database missing tags table, adding...")
    db.execute(
        "CREATE TABLE tags ("
        "annotation_id INTEGER PRIMARY KEY,"
        "still_id INTEGER,"
        "tag_id INTEGER"
        ");")
    db.commit()
# - labels: (still id[int], label id[int], x[int], y[int])
if not table_exists(db, 'labels'):
    logging.info("database missing labels table, adding...")
    db.execute(
        "CREATE TABLE labels ("
        "annotation_id INTEGER PRIMARY KEY,"
        "still_id INTEGER,"
        "label_id INTEGER,"
        "x INTEGER,"
        "y INTEGER"
        ");")
    db.commit()
# - bbox_labels: (bbox_label_id[int], name[str])
if not table_exists(db, 'bbox_labels'):
    db.execute(
        "CREATE TABLE bbox_labels ("
        "bbox_label_id INTEGER PRIMARY KEY,"
        "name TEXT"
        ");")
    db.commit()
# - bboxes: (
#    bbox_id[int], still_id[int], label_id[int],
#    left[real], top[real], right[real], bottom[real])
if not table_exists(db, 'bboxes'):
    db.execute(
        "CREATE TABLE bboxes ("
        "bbox_id INTEGER PRIMARY KEY,"
        "still_id INTEGER,"
        "label_id INTEGER,"
        "left REAL,"
        "top REAL,"
        "right REAL,"
        "bottom REAL"
        ");")
    db.commit()


def load_lookups_from_table(table_name):
    table = dict(db.execute("SELECT * FROM " + table_name).fetchall())
    rtable = {v: k for (k, v) in table.items()}
    assert len(table) == len(rtable)
    return table, rtable


tags, rtags = load_lookups_from_table('tag_names')
labels, rlabels = load_lookups_from_table('label_names')
bbox_labels, rbbox_labels = load_lookups_from_table('bbox_labels')
# tag_names_by_code = db.execute(
#     "SELECT tag_id, name FROM tag_names").fetchall()
# tags = dict(tag_names_by_code)
# 
# label_names_by_code = db.execute(
#     "SELECT label_id, name FROM label_names").fetchall()
# if len(label_names_by_code) == 0:
#     labels = {0: 'note', 1: 'flower', 2: 'pollinator'}
# else:
#     labels = dict(label_names_by_code)
# 
# bbox_labels_by_code = db.execute(
#     "SELECT bbox_label_id, name FROM bbox_labels").fetchall()
# if len(label_names_by_code) == 0:
#     bbox_labels = {}
# else:
#     bbox_labels = dict(bbox_labels_by_code)
 
annotation_template = {
    "version": "4.5.6",
    "shapes": [],
    "imagePath": "",  # fill with tfn
    "imageData": None,
    "imageHeight": 1944,
    "imageWidth": 2592,
}
shape_template = {
    "label": "",  # fill with label
    "points": [],  # append [x, y] as list
    "groupd_id": None,
    "shape_type": "point",
    "flags": {},
}
flags_template = {name: False for name in iter(tags.values())}

#rtags = {v: k for (k, v) in tags.items()}
#rlabels = {v: k for (k, v) in labels.items()}
#rbbox_labels = {v: k for (k, v) in labels.items()}

# get fns from database selecting for camera and time
file_infos = []

# subset by start/end tagged images
if args.start_end_limit:
    found_start = False
    found_end = False
for s in db.execute(
        "SELECT * FROM stills WHERE "
        "camera_id=? AND "
        "timestamp>=? AND timestamp<=?;",
        (args.camera_id, min_time, max_time)):
    still_id, args.camera_id, timestamp, path = s
    if args.start_end_limit:
        if found_end:
            # end was added on the previous iteration
            break
        image_tags = [r[0] for r in db.execute(
            'SELECT tag_id FROM tags WHERE still_id=?', (still_id, )).fetchall()]
        if not found_start:
            if rtags['start'] in image_tags:
                found_start = True
            else:
                continue
        else:
            if rtags['end'] in image_tags:
                found_end = True
    file_infos.append({
        'path': os.path.join(args.data_dir, path),
        'timestamp': timestamp,
        'camera_id': args.camera_id,
        'still_id': still_id})
if len(file_infos) == 0:
    raise Exception("No files found")
print("{} files found".format(len(file_infos)))
#images_dir = 'images/'
#fns = sorted(glob.glob(os.path.join(images_dir + '*')))

if not os.path.exists(args.tmp_dir):
    os.makedirs(args.tmp_dir)

# clean up files in temp directory
if args.resume:
    previous_image_fns = []
    print("Resuming previous annotation, keeping old files")
    for tfn in os.listdir(args.tmp_dir):
        # add all image files to list to check that these match
        # what should be added
        if os.path.splitext(tfn)[1] == '.jpg':
            previous_image_fns.append(tfn)
else:
    for tfn in os.listdir(args.tmp_dir):
        os.remove(os.path.join(args.tmp_dir, tfn))


# symlink files to temp directory
#ndigits = int(math.log10(len(fns)) + 1)
ndigits = int(math.log10(len(file_infos)) + 1)
fn_indices = {}
previously_annotated_images = set()
for (index, fi) in enumerate(file_infos):
    fn = fi['path']
    ts = fi['timestamp'].strftime('%y%m%d_%H%M')
    still_id = fi['still_id']
    ext = os.path.splitext(fn)[1].strip('.')

    # make descriptive filename: add time
    tfn = '.'.join((
        str(index).zfill(ndigits) +
        f'_{args.camera_id}_{ts}',
        ext))

    fn_indices[tfn] = index

    if args.resume:
        try:
            previous_image_fns.remove(tfn)
        except ValueError:
            # found file in db that wasn't in temp files
            print("Failing to resume because temp files do not match db files")
            raise Exception(f"Found file in db that wasn't in temp files: {tfn}")
        continue

    os.symlink(os.path.abspath(fn), os.path.join(args.tmp_dir, tfn))

    previous_tags = []
    for r in db.execute("SELECT tag_id FROM tags WHERE still_id=?", (still_id, )):
        logging.debug(f"Found previous tag {r} for {still_id}")
        previously_annotated_images.add(still_id)
        previous_tags.append(tags[r[0]])

    previous_labels = []
    for r in db.execute(
            "SELECT label_id, x, y FROM labels WHERE still_id=?", (still_id, )):
        logging.debug(f"Found previous point {r} for {still_id}")
        previously_annotated_images.add(still_id)
        previous_labels.append({
            'name': labels[r[0]],
            'xy': (r[1], r[2]),
        })

    previous_bboxes = []
    for r in db.execute(
            "SELECT label_id, left, top, right, bottom FROM bboxes WHERE still_id=?",
            (still_id, )):
        logging.debug(f"Found previous bboxes {r} for {still_id}")
        previously_annotated_images.add(still_id)
        previous_bboxes.append({
            'name': bbox_labels[r[0]],
            'points': [[r[1], r[2]], [r[3], r[4]]],
        })

    # write out json for any previous annotations
    if len(previous_tags) or len(previous_labels) or len(previous_bboxes):
        annotation = copy.deepcopy(annotation_template)
        annotation['flags'] = copy.deepcopy(flags_template)
        for tag in previous_tags:
            annotation['flags'][tag] = True
        for label in previous_labels:
            shape = copy.deepcopy(shape_template)
            shape["label"] = label["name"]
            shape["points"].append(label["xy"])
            annotation['shapes'].append(shape)
        for bbox in previous_bboxes:
            shape = copy.deepcopy(shape_template)
            shape['shape_type'] = 'rectangle'
            shape['label'] = bbox['name']
            shape['points'] = bbox['points']
            annotation['shapes'].append(shape)
        annotation["imagePath"] = tfn
        jfn = os.path.join(args.tmp_dir, os.path.splitext(tfn)[0] + ".json")
        with open(jfn, "w") as f:
            json.dump(annotation, f)

if args.resume and len(previous_image_fns) != 0:
    print("Files in tmp that weren't in db: ", previous_image_fns)
    raise Exception("Failing to resume because not all temp files were found in db")

# run labelme to annotate images
# some tag and label names have spaces, will these work in command or
# will they need to be written to a separate file?
#tag_names = "'" + ",".join(sorted(list(tags.values()))) + "'"
tag_names = ",".join(sorted(list(tags.values())))
#label_names = (
#    "'" +
#    ",".join(sorted(set(labels.values()).union(set(bbox_labels.values())))) +
#    ",")
label_names = ",".join(sorted(set(labels.values()).union(set(bbox_labels.values()))))
cmd = [
    "labelme",
    args.tmp_dir,
    "--config",
    "labelmerc",
    "--flags",
    tag_names,
    "--labels",
    label_names,
]
subprocess.check_call(cmd)

# remove all old annotations for this camera/date
for still_id in previously_annotated_images:
    logging.debug(f"Removing previous annotations for {still_id}")
    db.execute("DELETE FROM tags WHERE still_id=?", (still_id, ))
    db.execute("DELETE FROM labels WHERE still_id=?", (still_id, ))
    db.execute("DELETE FROM bboxes WHERE still_id=?", (still_id, ))

# parse annotations
annotation_filenames = sorted(glob.glob(os.path.join(args.tmp_dir, '*.json')))
for afn in annotation_filenames:
    # load and parse annotation
    with open(afn, 'r') as f:
        data = json.load(f)

        index = fn_indices[data["imagePath"]]
        info = file_infos[index]
        still_id = info['still_id']
        logging.debug(f"Found annotations for {still_id}")

        # save flags
        flags = data['flags']
        for flag in data["flags"]:
            if data["flags"][flag]:
                tag_id = rtags[flag]
                # add flag/tag to database (if not already there)
                if not db.execute(
                        "SELECT tag_id FROM tags WHERE "
                        "still_id=? AND tag_id=?", (still_id, tag_id)).fetchone():
                    logging.debug(f"\tinserting tag {tag_id} into database")
                    db.execute(
                        "INSERT INTO tags (still_id, tag_id) VALUES (?, ?);",
                        (still_id, tag_id))
                    db.commit()

        # save labels
        for s in data['shapes']:
            if s['shape_type'] == 'point':
                pts = s['points']
                assert len(pts) == 1
                x, y = pts[0]
                # check for new label
                if s['label'] not in rlabels:
                    # insert into database
                    db.execute(
                        'INSERT INTO label_names (name) VALUES (?);',
                        (s['label'], ))
                    db.commit()
                    # reload labels
                    labels, rlabels = load_lookups_from_table('label_names')
                label_id = rlabels[s['label']]
                datum = (still_id, label_id, int(x), int(y))
                if not db.execute(
                        "SELECT label_id FROM labels WHERE "
                        "still_id=? AND label_id=? AND x=? AND y=?", datum).fetchone():
                    logging.debug(f"\tinserting point{datum[1:]} into database")
                    db.execute(
                        "INSERT INTO labels (still_id, label_id, x, y) "
                        "VALUES (?, ?, ?, ?);", datum)
                    db.commit()
            elif s['shape_type'] == 'rectangle':
                pts = s['points']
                assert len(pts) == 2
                (x0, y0), (x1, y1) = pts[0], pts[1]
                top, bottom = (y0, y1) if y0 < y1 else (y1, y0)
                left, right = (x0, x1) if x0 < x1 else (x1, x0)
                # check for new bbox_label
                if s['label'] not in rbbox_labels:
                    # insert into database
                    db.execute(
                        'INSERT INTO bbox_labels (name) VALUES (?);',
                        (s['label'], ))
                    db.commit()
                    # reload labels
                    bbox_labels, rbbox_labels = load_lookups_from_table('bbox_labels')
                label_id = rbbox_labels[s['label']]
                datum = (still_id, label_id, left, top, right, bottom)
                if not db.execute(
                        "SELECT bbox_id FROM bboxes WHERE "
                        "still_id=? AND label_id=? AND left=? AND top=? "
                        "AND right=? AND bottom=?", datum).fetchone():
                    logging.debug(f"\tinserting bbox{datum[1:]} into database")
                    db.execute(
                        "INSERT INTO bboxes"
                        "(still_id, label_id, left, top, right, bottom) "
                        "VALUES (?, ?, ?, ?, ?, ?);", datum)
            else:
                logging.warning(f"\tinvalid shape type {s['shape_type']}")
                continue

# write annotations to disk
db.commit()
db.close()

# everything finished, increment date, write options to file
next_day = day + datetime.timedelta(days=1)
next_day_str = next_day.strftime('%y%m%d')
logging.debug(f"Incrementing day {next_day_str}")
for option in options:
    name, _, default = option
    if name == 'date':
        cfg[name] = next_day_str
    else:
        cfg[name] = getattr(args, name)
with open(cfg_fn, 'w') as f:
    logging.debug(f"Writing to {cfg_fn}: {cfg}")
    json.dump(cfg, f)
