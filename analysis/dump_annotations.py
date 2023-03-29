import datetime
import logging
import os
import sqlite3
import sys
import time

raise Exception("Failed to copy PRIMARY KEY column attribute")

ts = datetime.datetime.now().strftime('%y%m%d')
db_fn = 'pcam.sqlite'
annotations_db_fn = f'{ts}.sqlite'

if os.path.exists(annotations_db_fn):
    response = None
    while response is None:
        response = input(f"File {annotations_db_fn} exists, overwrite (y/n)?")
        response = response.strip().lower()
        if len(response) < 1:
            print(f"Invalid response try again")
        if response[0] == 'n':
            sys.exit(1)
        elif response[0] == 'y':
            break
        print(f"Invalid response try again")
        response = None


# open db
original_db = sqlite3.connect(db_fn, detect_types=sqlite3.PARSE_DECLTYPES)
original_db.execute("ATTACH DATABASE '" + annotations_db_fn + "' AS other;")
# create tables in
original_db.execute(
    "CREATE TABLE IF NOT EXISTS other.tag_names "
    "AS SELECT * FROM main.tag_names WHERE 0;")
original_db.execute(
    "CREATE TABLE IF NOT EXISTS other.tags "
    "AS SELECT * FROM main.tags WHERE 0;")
original_db.execute(
    "CREATE TABLE IF NOT EXISTS other.labels "
    "AS SELECT * FROM main.labels WHERE 0;")
original_db.execute(
    "CREATE TABLE IF NOT EXISTS other.label_names "
    "AS SELECT * FROM main.label_names WHERE 0;")
original_db.execute("INSERT INTO other.tag_names SELECT * FROM main.tag_names")
original_db.execute("INSERT INTO other.tags SELECT * FROM main.tags")
original_db.execute("INSERT INTO other.label_names SELECT * FROM main.label_names")
original_db.execute("INSERT INTO other.labels SELECT * FROM main.labels")
original_db.commit()
original_db.execute("DETACH other;")
original_db.close()
