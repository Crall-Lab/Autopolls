import sqlite3


primary_keys_by_table = {
    'cameras': 'camera_id',
    'configs': 'config_id',
    'detections': 'detection_id',
    'videos': 'video_id',
    'stills': 'still_id',
    'crude_results': 'still_id',
    'tags': 'annotation_id',
    'tag_names': 'tag_id',
    'labels': 'annotation_id',
    'label_names': 'label_id',
    'bboxes': 'bbox_id',
    'bbox_labels': 'bbox_label_id',
}

schema_by_table = {
    # skip cameras, configs, detections, videos, stills, crude_results
    'tags': "CREATE TABLE {} (annotation_id INTEGER PRIMARY KEY, still_id INTEGER, tag_id INTEGER);",
    'tag_names': "CREATE TABLE {} (tag_id INTEGER PRIMARY KEY, name TEXT);",
    'labels': "CREATE TABLE {} (annotation_id INTEGER PRIMARY KEY, still_id INTEGER, label_id INTEGER, x INTEGER, y INTEGER);",
    'label_names': "CREATE TABLE {} (label_id INTEGER PRIMARY KEY, name TEXT);",
    'bboxes': "CREATE TABLE {} (bbox_id INTEGER PRIMARY KEY, still_id INTEGER, label_id INTEGER, left REAL, top REAL, right REAL, bottom REAL);",
    'bbox_labels': "CREATE TABLE {} (bbox_label_id INTEGER PRIMARY KEY, name TEXT);",
}

db_fn = 'pcam.sqlite'

db = sqlite3.connect(db_fn, detect_types=sqlite3.PARSE_DECLTYPES)

# look for tables with missing primary keys
# make a new table with the correct primary key
# check for data where the key is None
# prompt user asking them to confirm
# copy over data

# save database
for table_row in db.execute("SELECT * FROM sqlite_master WHERE type='table';").fetchall():
    _, name, _, _, sql = table_row

    print(f"Found table: {name}")

    # check for a column listed as a primary key
    if 'PRIMARY KEY' in sql:
        print(f"\thas PRIMARY KEY: {sql}")
        continue

    # missing primary key
    if name not in primary_keys_by_table:
        raise Exception(f"Found unknown table[{name}] with missing primary key")

    # check for 'bad' values: where primary key is None or not unique
    primary_key = primary_keys_by_table[name]

    # TODO options to renumber?
    # for 'tags' renumber all items that have annotation_id IS None
    # for 'tags' renumber all non-unique annotation_id items
    # for 'labels' renumber all items that have label_id IS None
    # for '

    # check for values where what should be the primary key is None
    bad_values = db.execute(f'SELECT * FROM {name} WHERE {primary_key} IS ?', (None, )).fetchall()
    if len(bad_values):
        print(f"\tfound {len(bad_values)} rows where primary key[{primary_key}] is None")
        print(f"\t\tExample: {bad_values[0]}")
        response = input(f"\tWould you like to delete these rows? [y]es/[n]o >> ")
        if len(response) and response.strip().lower()[0] == 'y':
            print(f"\t\tDeleting {len(bad_values)} rows")
            db.execute(f'DELETE FROM {name} WHERE {primary_key} IS ?', (None, ))
            db.commit()
            bad_values = db.execute(f'SELECT * FROM {name} WHERE {primary_key} IS ?', (None, )).fetchall()
            if len(bad_values):
                raise Exception("Failed to delete bad values")

    # check for non-unique values
    non_unique_ids = db.execute(f'SELECT {primary_key}, count(*) FROM {name} GROUP BY {primary_key} HAVING count(*) > 1').fetchall()
    if len(non_unique_ids):
        print(f"\tFound {len(non_unique_ids)} non-unique primary keys")
        response = input(f"\tWould you like to delete these rows? [y]es/[n]o >> ")
        if len(response) and response.strip().lower()[0] == 'y':
            for non_unique_id in non_unique_ids:
                bad_id, count = non_unique_id
                print(f"\tfound {count} rows with the same id {bad_id}")
                example = db.execute(f'SELECT * FROM {name} WHERE {primary_key}=?', (bad_id, )).fetchone()
                print(f"\t\tExample: {example}")
                print(f"\t\tDeleting {count} rows")
                db.execute(f'DELETE FROM {name} WHERE {primary_key}=?', (bad_id, ))
                db.commit()
                vs = db.execute(f'SELECT * FROM {name} WHERE {primary_key}=?', (bad_id, )).fetchall()
                if len(vs):
                    raise Exception(f"Failed to delete rows with id {bad_id}")

    # check for values where the pi

    # get number of values from old table
    n_values = db.execute(f'SELECT COUNT(*) FROM {name};').fetchone()[0]

    # make a new table with correct schema
    new_name = name + '_new'
    if new_name in primary_keys_by_table:
        raise Exception(f"Failed to make unique new name [{new_name}]")

    if name not in schema_by_table:
        raise Exception(f"Missing schema for table {name}")

    schema = schema_by_table[name].format(new_name)
    db.execute(schema)

    # copy over values
    if name == 'bboxes':
        bboxes = db.execute("SELECT bbox_id, still_id, label_id, left, top, right, bottom FROM bboxes").fetchall()
        for bbox in bboxes:
            db.execute(f"INSERT INTO {new_name} (bbox_id, still_id, label_id, left, top, right, bottom) VALUES (?, ?, ?, ?, ?, ?, ?)", bbox)
        db.commit()
    else:
        db.execute(f"INSERT INTO {new_name} SELECT * FROM {name}")
        db.commit()
    new_n_values = db.execute(f'SELECT COUNT(*) FROM {new_name};').fetchone()[0]
    if new_n_values != n_values:
        raise Exception(f"Failed to copy over values: {new_n_values} != {n_values}")

    # drop old table
    db.execute(f"DROP TABLE {name};")
    db.commit()
    # rename new to old
    db.execute(f"ALTER TABLE {new_name} RENAME TO {name};")
    db.commit()

