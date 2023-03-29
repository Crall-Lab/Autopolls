import datetime
import logging
import os
import sqlite3
import sys
import time


db_fn = 'pcam.sqlite'
annotations_db_fn = '210406_with_210525_flowers_fixed_schema_210621.sqlite'

tables = ('tags', 'tag_names', 'labels', 'label_names', 'bboxes', 'bbox_labels')
schema_by_table = {
    'tags': "CREATE TABLE {} (annotation_id INTEGER PRIMARY KEY, still_id INTEGER, tag_id INTEGER);",
    'tag_names': "CREATE TABLE {} (tag_id INTEGER PRIMARY KEY, name TEXT);",
    'labels': "CREATE TABLE {} (annotation_id INTEGER PRIMARY KEY, still_id INTEGER, label_id INTEGER, x INTEGER, y INTEGER);",
    'label_names': "CREATE TABLE {} (label_id INTEGER PRIMARY KEY, name TEXT);",
    'bboxes': "CREATE TABLE {} (bbox_id INTEGER PRIMARY KEY, still_id INTEGER, label_id INTEGER, left REAL, top REAL, right REAL, bottom REAL);",
    'bbox_labels': "CREATE TABLE {} (bbox_label_id INTEGER PRIMARY KEY, name TEXT);",
}
assert all([t in schema_by_table for t in tables]) 

response = None
while response is None:
    response = input(
        f"You want to delete annotations in {db_fn} and copy annotatoins from {annotations_db_fn} (y/n)?")
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
# drop annotation tables
for table_name in tables:
    print(f"dropping {table_name} in {db_fn}")
    original_db.execute(f"DROP TABLE IF EXISTS {table_name};")

original_db.execute("ATTACH DATABASE '" + annotations_db_fn + "' AS other;")

# create tables in original database
for table_name in tables:
    print(f"copying {table_name}")
    #original_db.execute(
    #    f"CREATE TABLE IF NOT EXISTS {table_name} " +
    #    f"AS SELECT * FROM other.{table_name} WHERE 0;")
    schema = schema_by_table[table_name].format(table_name)
    original_db.execute(schema)
    original_db.execute(f"INSERT INTO {table_name} SELECT * FROM other.{table_name}")

original_db.commit()
original_db.execute("DETACH other;")
original_db.close()
