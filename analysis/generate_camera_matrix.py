"""
For each camera get all days that have images
Output a matrix with cameras as columns (1-N)
and days as rows with first row being earliest day from all cameras
and last row being latest day from all cameras
and each cell containing a count of images
"""
import datetime
import sqlite3


db = sqlite3.connect("pcam.sqlite", detect_types=sqlite3.PARSE_DECLTYPES)

# count camera/module pairs
camera_ids = [r[0] for r in db.execute("SELECT camera_id FROM cameras").fetchall()]
print("{} camera/modules pairs".format(len(camera_ids)))

earliest = datetime.datetime.strptime(
    db.execute("SELECT MIN(timestamp) FROM stills").fetchone()[0],
    "%Y-%m-%d %H:%M:%S")
latest = datetime.datetime.strptime(
    db.execute("SELECT MAX(timestamp) FROM stills").fetchone()[0],
    "%Y-%m-%d %H:%M:%S")

start = earliest.replace(hour=0, minute=0, second=0)
one_day = datetime.timedelta(days=1)

with open("camera_matrix.csv", "w") as f:
    # write camera id header
    f.write("," + ",".join(map(str, camera_ids)) + "\n")
    # write each row
    while start < latest:
        f.write(start.strftime("%y%m%d"))
        for cid in camera_ids:
            # count n images for each camera
            n_images = db.execute(
                "SELECT COUNT(timestamp) FROM stills "
                "WHERE camera_id=? AND timestamp>=? AND timestamp<=?",
                (cid, start, start + one_day)
            ).fetchone()[0]
            print(f"{cid},{start},{n_images}")
            f.write(f",{n_images}")
        f.write("\n")
        start += one_day
