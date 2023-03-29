import sqlite3


annotations_db_filename = '../210406_with_210512_flowers.sqlite'

db = sqlite3.connect(annotations_db_filename, detect_types=sqlite3.PARSE_DECLTYPES)

# read all bounding box labels
labels_by_code = dict(db.execute(
        "SELECT bbox_label_id, name FROM bbox_labels").fetchall())
# count bounding boxes by species
counts_by_label_id = db.execute(
    "SELECT label_id, COUNT(*) FROM bboxes GROUP BY label_id").fetchall()
counts_by_label_id = sorted(counts_by_label_id, key=lambda i: i[1])

print("Per-species bounding box counts")
for count_result in counts_by_label_id:
    label_id, count = count_result
    name = labels_by_code[label_id]
    print(f"\t{count}:\t{name}")
