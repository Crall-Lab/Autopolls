import os
import sqlite3


data_dir = '/media/graham/377CDC5E2ECAB822'
db_fn = '../pcam.sqlite'
annotations_db_fn = '../210318.sqlite'
tmp_dir = 'tmp'

db = sqlite3.connect(db_fn, detect_types=sqlite3.PARSE_DECLTYPES)
annotations_db = sqlite3.connect(annotations_db_fn, detect_types=sqlite3.PARSE_DECLTYPES)


tag_ids = annotations_db.execute(
    "SELECT tag_id FROM tag_names WHERE name='start'").fetchall()
assert len(tag_ids) == 1
start_tag_id = tag_ids[0]

still_ids = sorted([
    i[0] for i in annotations_db.execute(
        "SELECT still_id FROM tags WHERE tag_id=?", start_tag_id).fetchall()])

def find_still_row(still_id):
    still_rows = db.execute(
        "SELECT * FROM stills WHERE still_id=?", (still_id, )).fetchall()
    if len(still_rows) == 0:
        raise Exception(f"Missing still[{still_id}] for tag[{aid}:{name}]")
    if len(still_rows) > 1:
        raise Exception(f"Multiple rows[{still_rows}] for tag[{aid}:{name}]")
    return still_rows[0]

print(f"Found {len(still_ids)} for annotating")

if os.path.exists(tmp_dir):
    raise Exception(
        f"Found existing tmp directory[{tmp_dir}], refusing to overwrite")
else:
    os.makedirs(tmp_dir)

for (index, still_id) in enumerate(still_ids):
    _, camera_id, timestamp, path = find_still_row(still_id)

    # link still to tmp directory for annotation
    fn = os.path.join(data_dir, path)
    tfn = '_'.join((
        str(index).zfill(6),
        str(camera_id),
        timestamp.strftime('%y%m%d_%H%M'))) + '.' + os.path.splitext(fn)[1].strip('.')
    os.symlink(os.path.abspath(fn), os.path.join(tmp_dir, tfn))

# TODO print out command to run
