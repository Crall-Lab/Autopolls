import sqlite3
import sys


if len(sys.argv) < 2:
    raise Exception("Missing species name")

# name of the species used to find annotations
species_name = sys.argv[1]
if species_name == '*' or species_name == 'all':
    species_name = ''

db_filename = 'pcam.sqlite'

db = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES)

# read all bounding box labels
labels_by_code = dict(db.execute(
        "SELECT bbox_label_id, name FROM bbox_labels").fetchall())

# find codes for species that match species_name
codes = []
print(f"Looking for species that match {species_name}")
for code in labels_by_code:
    name = labels_by_code[code]
    if species_name in name:
        print(f"Query matched species: {name}")
        codes.append(code)

# find all periods for this species by
for code in sorted(codes, key=lambda c: labels_by_code[c]):
    species = labels_by_code[code]
    print(f"For species: {species}")

    # first finding stills for bounding boxes with these annotations
    # bbox_id, still_id, label_id, left, top, right, bottom
    bboxes = db.execute(
        "SELECT * FROM bboxes WHERE label_id=?", (code, )).fetchall()
    print(f"\tfound {len(bboxes)} bounding boxes")

    # periods = [(day, camera), ]
    periods = {}
    for bbox in bboxes:
        still_id = bbox[1]
        r = db.execute(
            "SELECT * FROM stills WHERE still_id=?", (still_id, )).fetchall()
        if len(r) != 1:
            raise Exception(
                f"Found invalid bounding box without still_id[{still_id}]: {bbox}")
        still_id, camera_id, timestamp, path = r[0]
        date = timestamp.strftime('%y%m%d')
        period = (date, camera_id)
        if period not in periods:
            periods[period] = []
        periods[period].append({
            'bounding_box': bbox,
            'still': r[0],
        })

    print(f"\tfound {len(periods)} periods (date/camera pairs)")
    print("\t\tcamera\tdate\tn_bboxes\tcounts per hour")
    for period in sorted(periods):
        date, camera_id = period
        n_bboxes = len(periods[period])

        counts_per_hour = [0] * 24
        for meta in periods[period]:
            ts = meta['still'][2]
            counts_per_hour[ts.hour] += 1

        sparkline = "".join([str(c) if c else '_' for c in counts_per_hour])
        print(f"\t\t{camera_id:2g}\t{date}\t{n_bboxes}\t{sparkline}")

## count bounding boxes by species
#counts_by_label_id = db.execute(
#    "SELECT label_id, COUNT(*) FROM bboxes GROUP BY label_id").fetchall()
#counts_by_label_id = sorted(counts_by_label_id, key=lambda i: i[1])
#   
#print("Per-species bounding box counts")
#for count_result in counts_by_label_id:
#    label_id, count = count_result
#    name = labels_by_code[label_id]
#    print(f"\t{count}:\t{name}")
