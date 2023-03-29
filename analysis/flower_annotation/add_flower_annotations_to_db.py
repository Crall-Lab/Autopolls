import datetime
import glob
import json
import os
import sqlite3


database_filename = '../pcam.sqlite'
annotations_db_filename = '../210406_fixed_schema_210621.sqlite'
annotation_directory = 'flower_annotations_210525'

dataset_db = sqlite3.connect(database_filename, detect_types=sqlite3.PARSE_DECLTYPES)
annotations_db = sqlite3.connect(annotations_db_filename, detect_types=sqlite3.PARSE_DECLTYPES)

# first prefetch all stills labeled start to use their timestamp to match annotations
start_code = annotations_db.execute(
    "SELECT tag_id FROM tag_names WHERE name='start'").fetchone()[0]
start_still_ids = annotations_db.execute(
    "SELECT still_id FROM tags WHERE tag_id=?", (start_code, )).fetchall()
stills_by_camera = {}
for still_id in start_still_ids:
    camera_id, timestamp = dataset_db.execute(
        "SELECT camera_id, timestamp FROM stills WHERE still_id=?", (still_id[0], )).fetchone()
    if camera_id not in stills_by_camera:
        stills_by_camera[camera_id] = {}
    timestamp_str = timestamp.strftime('%y%m%d_%H%M')
    assert timestamp_str not in stills_by_camera[camera_id]
    stills_by_camera[camera_id][timestamp_str] = still_id[0]


def find_still_id(camera, timestamp):
    timestamp_str = timestamp.strftime('%y%m%d_%H%M')
    return stills_by_camera[camera][timestamp_str]


def load_json_annotations(directory):
    annotations = []
    for fn in sorted(glob.glob(os.path.join(directory, '*.json'))):
        with open(fn, 'r') as f:
            d = json.load(f)

            # read in flags/tags
            tags = {}
            for k in d['flags']:
                if d['flags'][k]:
                    tags[k] = True

            # read in shapes, make sure all are rectangles
            bboxes = []
            for shape in d['shapes']:
                if shape['shape_type'] != 'rectangle':
                    raise Exception(
                        f"Invalid non-rectangle shape: {shape['shape_type']}")
                (x0, y0), (x1, y1) = shape['points'][0], shape['points'][1]
                top, bottom = (y0, y1) if y0 < y1 else (y1, y0)
                left, right = (x0, x1) if x0 < x1 else (x1, x0)
                bboxes.append({
                    'top': top, 'left': left,
                    'bottom': bottom, 'right': right,
                    'label': shape['label']})

            # find corresponding still_id using filename:
            # <index>_<camera_id>_<yymmdd_hhmm>.jpg
            tokens = d['imagePath'].split('.')[0].split('_')
            assert len(tokens) == 4, "Invalid number of filename tokens"
            camera_id = int(tokens[1])
            timestamp_string = "_".join((tokens[2], tokens[3]))
            timestamp = datetime.datetime.strptime(
                timestamp_string, '%y%m%d_%H%M')
            still_id = find_still_id(camera_id, timestamp)

            annotations.append({
                'still_id': still_id,
                'timestamp': timestamp,
                'bboxes': bboxes,
                'tags': tags,
            })
    return annotations


def index_annotations(annotations):
    all_tags = set([])
    bbox_labels = set([])
    for a in annotations:
        for t in a['tags']:
            all_tags.add(t)
        for b in a['bboxes']:
            bbox_labels.add(b['label'])
    return sorted(list(all_tags)), sorted(list(bbox_labels))


def table_exists(db, table_name):
    res = db.execute("SELECT name from sqlite_master WHERE type='table';")
    for r in res:
        if r[0] == table_name:
            return True
    return False


def read_tag_names(db):
    # get existing tag names
    tag_names_by_code = dict(db.execute(
        "SELECT tag_id, name FROM tag_names").fetchall())
    tag_codes_by_name = {v: k for k, v in tag_names_by_code.items()}
    assert len(tag_names_by_code) == len(tag_codes_by_name)
    return tag_names_by_code, tag_codes_by_name


def read_bbox_labels(db):
    bbox_labels_by_code = dict(db.execute(
        "SELECT bbox_label_id, name FROM bbox_labels").fetchall())
    bbox_labels_by_name = {v: k for k, v in bbox_labels_by_code.items()}
    assert len(bbox_labels_by_code) == len(bbox_labels_by_name)
    return bbox_labels_by_code, bbox_labels_by_name


def add_tag_names_to_db(db, tags):
    # get existing tag names
    tag_names_by_code, tag_codes_by_name = read_tag_names(db)
    print(f"Found existing tags: {tag_names_by_code}")
    next_code = max([-1, ] + list(tag_names_by_code.keys())) + 1

    # skip adding tag names that are already in the database
    for tag in tags:
        if tag in tag_codes_by_name:
            print(f"Skipping adding tag[{tag}] to database")
            continue
        print(f"Adding tag[{tag}] to database")
        db.execute(
            "INSERT INTO tag_names (tag_id, name) VALUES (?, ?);",
            (next_code, tag, ))
        next_code += 1
    db.commit()


def add_bbox_labels_to_db(db, bbox_labels):
    # if no bbox_labels table exists, create it
    if not table_exists(db, 'bbox_labels'):
        db.execute(
            "CREATE TABLE bbox_labels ("
            "bbox_label_id INTEGER PRIMARY KEY,"
            "name TEXT"
            ");")
        db.commit()
    # get existing bbox labels
    bbox_labels_by_code, bbox_codes_by_label = read_bbox_labels(db)
    next_code = max([-1, ] + list(bbox_labels_by_code.keys())) + 1

    # skip adding bbox labels that are already in the database
    for bbox_label in bbox_labels:
        if bbox_label in bbox_codes_by_label:
            continue
        print(f"Adding bbox_label{bbox_label}] to database")
        db.execute(
            "INSERT INTO bbox_labels (bbox_label_id, name) VALUES (?, ?);",
            (next_code, bbox_label))
        next_code += 1
    db.commit()


def add_annotations_to_db(db, annotations):
    if not table_exists(db, 'tags'):
        raise Exception("database missing tags table")
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

    tags_by_code, tags_by_name = read_tag_names(db)
    labels_by_code, labels_by_label = read_bbox_labels(db)

    next_tag_id = db.execute("SELECT MAX(annotation_id) FROM tags").fetchone()[0]
    if next_tag_id is None:
        next_tag_id = 0
    else:
        next_tag_id += 1
    next_bbox_id = db.execute("SELECT MAX(bbox_id) FROM bboxes").fetchone()[0]
    if next_bbox_id is None:
        next_bbox_id = 0
    else:
        next_bbox_id += 1

    for a in annotations:
        print(f"Annotations for {a['still_id']}")
        for b in a['bboxes']:
            code = labels_by_label[b['label']]
            print(f"\tbounding box for {b['label']}")
            db.execute(
                "INSERT INTO bboxes "
                "(bbox_id, still_id, label_id, left, top, right, bottom) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    next_bbox_id, a['still_id'], code,
                    b['left'], b['top'], b['right'], b['bottom']))
            next_bbox_id += 1
        for t in a['tags']:
            if not a['tags'][t]:
                continue
            print(f"\ttag {t}")
            code = tags_by_name[t]
            db.execute(
                "INSERT INTO tags (annotation_id, still_id, tag_id) "
                "VALUES (?, ?, ?)", (next_tag_id, a['still_id'], code))
            next_tag_id += 1
        db.commit()


if __name__ == '__main__':
    annotations = load_json_annotations(annotation_directory)

    # get lists of all unique tags and bbox labels
    all_tags, all_labels = index_annotations(annotations)
    print(f"Found tags: {all_tags}")
    print(f"Found bbox_labels: {all_labels}")

    # add these lists to the db
    add_tag_names_to_db(annotations_db, all_tags)
    add_bbox_labels_to_db(annotations_db, all_labels)

    # using the code dictionaries, add all annotations to db
    add_annotations_to_db(annotations_db, annotations)
