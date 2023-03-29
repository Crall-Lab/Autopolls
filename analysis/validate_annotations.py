import datetime
import sqlite3


db_filename ='pcam.sqlite'
annotations_filename = '210208.sqlite'
camera_matrix_filename = 'camera_matrix.csv'

day_camera_matrix = []  # [date_index][camera_id-1] = {}
days = []
with open(camera_matrix_filename, 'r') as f:
    cids = [int(i) for i in f.readline().strip().split(',')[1:]]  # camera_id header
    # verify cids are 1-N
    for i, cid in enumerate(cids):
        assert cid == i + 1
    for l in f:
        tokens = l.strip().split(',')
        if len(tokens) == 0:
            continue
        date_string = tokens.pop(0)
        date = datetime.datetime.strptime(date_string, '%y%m%d').date()
        days.append(date)
        row = []
        for i, n_images in enumerate(tokens):
            cid = i + 1
            n_images = int(n_images)
            to_annotate = n_images > 0  # if 0, no data
            row.append({
                'n_images': n_images,
                'to_annotate': n_images > 0,
            })
        day_camera_matrix.append(row)

db = sqlite3.connect(
    db_filename, detect_types=sqlite3.PARSE_DECLTYPES)

annotations_db = sqlite3.connect(
    annotations_filename, detect_types=sqlite3.PARSE_DECLTYPES)

# load tag_names [tag_id, name]
tag_names = {
    r[0]: r[1] for r in annotations_db.execute(
        "SELECT * FROM tag_names").fetchall()}
# load label_names [label_id, name]
label_names = {
    r[0]: r[1] for r in annotations_db.execute(
        "SELECT * FROM label_names").fetchall()}

# tables:
# - tags [annotation_id, still_id, tag_id]
# - labels [annotation_id, still_id, label_id, x, y]

# for each annotation (tag/label)
# - find still image
# - is day fully annotated? [has start/end] [can have multiple if camera moved]
# - render out start & end tags on day


def find_still_row(still_id):
    still_rows = db.execute(
        "SELECT * FROM stills WHERE still_id=?", (still_id, )).fetchall()
    if len(still_rows) == 0:
        raise Exception(f"Missing still[{still_id}] for tag[{aid}:{name}]")
    if len(still_rows) > 1:
        raise Exception(f"Multiple rows[{still_rows}] for tag[{aid}:{name}]")
    return still_rows[0]


tags_by_day_camera = {}
# tags = []
for r in annotations_db.execute("SELECT * FROM tags").fetchall():
    aid, still_id, tag_id = r
    name = tag_names[tag_id]
    _, camera_id, timestamp, path = find_still_row(still_id)  # first item is still_id
    tag = {
        'name': name, 'tag_id': tag_id,
        'still_id': still_id, 'timestamp': timestamp,
        'camera_id': camera_id}
    # tags.append(tag)
    # index annotations by day: timestamp.date()
    day = timestamp.date()
    if day not in tags_by_day_camera:
        tags_by_day_camera[day] = {}
    if camera_id not in tags_by_day_camera[day]:
        tags_by_day_camera[day][camera_id] = []
    tags_by_day_camera[day][camera_id].append(tag)


# does each annotated camera+day have at least 1 start and end
for day in tags_by_day_camera:
    for camera_id in tags_by_day_camera[day]:
        tags = tags_by_day_camera[day][camera_id]
        has_start = False
        has_end = False
        for tag in tags:
            if tag['name'] == 'start':
                has_start = True
            if tag['name'] == 'end':
                has_end = True
        if not has_start:
            print(f"Day[{day}] and camera[{camera_id}] missing start tag")
        if not has_end:
            print(f"Day[{day}] and camera[{camera_id}] missing end tag")
        if has_start and has_end:  # annotated
            day_camera_matrix[days.index(day)][camera_id-1]['annotated'] = True

# print out all days
# "1".rjust(2)
# 201004  0  1
# print out header
ncids = len(day_camera_matrix[0])
print("       " + " ".join([str(i).rjust(2) for i in range(1, ncids+1)]))
for (i, row) in enumerate(day_camera_matrix):
    date = days[i]
    print(date.strftime('%y%m%d'), end="")
    for c in row:
        if c.get('annotated', False):
            print(" \U0001f44d", end="")
        elif c['to_annotate']:
            print("  0", end="")
        else:
            print("  -", end="")
    print()


labels = []
for r in annotations_db.execute("SELECT * FROM labels").fetchall():
    aid, still_id, label_id, x, y = r
    name = label_names[label_id]
    _, camera_id, timestamp, path = find_still_row(still_id)  # first item is still_id
# generate a montage of some flowers
# generate a moontage of some pollinators
