import sqlite3
import sys


if len(sys.argv) < 2:
    raise Exception("Missing species name")

tag_name = sys.argv[1]

db_filename = 'pcam.sqlite'
db = sqlite3.connect(db_filename, detect_types=sqlite3.PARSE_DECLTYPES)


def print_and_find_name(tag_name):
    tagnames_by_code = dict(db.execute(
            "SELECT tag_id, name FROM tag_names").fetchall())

    print(f"Current tags in {db_filename}:")
    found = False
    for tag_id in tagnames_by_code:
        name = tagnames_by_code[tag_id]
        print(f"\t{tag_id:03d}: {name}")
        if tag_name == name:
            found = True
    return found


if print_and_find_name(tag_name):
    print(f"Tag name {tag_name} already in {db_filename}, doing nothing")
    sys.exit(0)

print(f"Are you certain you want to add the '{tag_name}' to {db_filename}?")

response = input("[y]es or [n]o?").lower()
if not len(response) or response[0] != 'y':
    print("aborting program without adding flag")
    sys.exit(0)

tag_id = db.execute("SELECT MAX(tag_id) FROM tag_names").fetchone()[0] + 1
db.execute("INSERT INTO tag_names (tag_id, name) VALUES (?, ?);", (tag_id, tag_name, ))
db.commit()

if not print_and_find_name(tag_name):
    raise Exception("Failed to add tag")

print("Success!")
