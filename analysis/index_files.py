import datetime
import glob
import logging
import os
import re
import sqlite3


data_dir = '/media/graham/377CDC5E2ECAB822'
dbfn = 'pcam.sqlite'
camera_info_fn = 'pcam_cameras_arboretum_grid.csv'
default_start_date = datetime.datetime.strptime('07/31/2020', '%m/%d/%Y')
default_end_date = datetime.datetime.strptime('10/08/2020', '%m/%d/%Y')

force = True
debug = False


if debug:
    logging.basicConfig(level=logging.DEBUG)


def read_camera_info_csv(fn, default_start_date, default_end_date):
    def get_prefix(m):
        if m in ('18c0', '1a5d', '1ac3', '1a80'):
            return "001f5443"
        # TODO '42b4'  ???
        return "001f543e"

    header = None
    info = []
    with open(fn, 'r') as f:
        for l in f:
            if header is None:  # skip first row
                header = l
                continue
            tokens = l.strip().split(',')[:6]
            assert len(tokens) == 6
            cid, mac, module, location, start, end = tokens
            cid = int(cid)
            mac = "{}{}".format(get_prefix(mac), mac).lower()
            module = int(module)
            if len(start.strip()) == 0:
                start = default_start_date
            else:
                start = datetime.datetime.strptime(start, '%m/%d/%Y')
            if len(end.strip()) == 0:
                end = default_end_date
            else:
                end = datetime.datetime.strptime(end, '%m/%d/%Y')
            info.append((cid, mac, module, location, start, end))
    return info


def get_modules():
    mps = sorted(glob.glob(os.path.join(data_dir, 'Module*')))
    modules = {}
    for mp in mps:
        index = int(os.path.split(mp)[-1].split('Module')[-1])
        if index in modules:
            raise Exception(f"Found 2 modules with same index {index}")
        modules[index] = mp
    return modules


def table_exists(db, table_name):
    res = db.execute("SELECT name from sqlite_master WHERE type='table';")
    for r in res:
        if r[0] == table_name:
            return True
    return False


def index_cameras(db, force=False):
    # check if camera table already exists
    if table_exists(db, 'cameras'):
        if not force:
            logging.warning("table cameras already exists, skipping")
            return False
        db.execute("DROP TABLE cameras;");
    info = read_camera_info_csv(camera_info_fn, default_start_date, default_end_date)
    # info[] (cid, mac, module, location, start, end)
    info_by_mac = {i[1]: i for i in info}
    logging.debug("{} cameras in info".format(len(info)))
    logging.info("creating cameras table")
    db.execute(
        "CREATE TABLE cameras ("
        "camera_id INTEGER PRIMARY KEY,"
        "mac TEXT,"
        "location TEXT,"
        "module INTEGER,"
        "start TIMESTAMP,"
        "end TIMESTAMP"
        ");")
    nc = 0
    modules = get_modules()
    found = {}
    extra = {}
    for module_index in modules:
        module_path = modules[module_index]
        logging.debug(f"Searching module {module_index} at {module_path}")
        camera_paths = sorted(glob.glob(os.path.join(module_path, '001f*')))
        for camera_path in camera_paths:
            macaddr = os.path.split(camera_path)[-1]
            extra[macaddr] = True
            logging.debug(f"Found camera {macaddr} in module {module_index}")
            if macaddr not in info_by_mac:
                logging.debug(f"Skipping camera[{macaddr}] that is not in info")
                continue
            cid, _, module, location, start, end = info_by_mac[macaddr]
            if module != module_index:
                logging.debug(
                    f"Skipping camera[{macaddr}], " +
                    f"module mismatch {module} != {module_index}")
                continue
            db.execute(
                "INSERT INTO cameras (camera_id, mac, location, module, start, end) " +
                "VALUES (?, ?, ?, ?, ?, ?);",
                (cid, macaddr, location, module_index, start, end))
            found[macaddr] = True
            del extra[macaddr]
            nc += 1
    #for m in found:
    #    print("Found {}".format(m))
    #for i in info:
    #    m = i[1]
    #    if m not in found:
    #        print("Lost {}".format(m))
    #for m in extra:
    #    print("Extra {}".format(m))
    logging.info(f"Found {nc} cameras")


def get_cameras(db, by_module_mac=True):
    if not table_exists(db, 'cameras'):
        raise Exception("Database missing cameras tabls")
    modules = get_modules()
    cameras = []
    for camera_row in db.execute('SELECT * FROM cameras'):
        camera_id, macaddr, location, module_index, start, end = camera_row
        cameras.append({
            'id': camera_id,
            'macaddr': macaddr,
            'location': location,
            'module_path': modules[module_index],
            'module_index': module_index,
            'start': start,
            'end': end,
        })
    if by_module_mac:
        d = {}
        for c in cameras:
            mi = c['module_index']
            if mi not in d:
                d[mi] = {}
            if c['macaddr'] in d[mi]:
                raise Exception(
                    "cameras are not unique {} appears >1 in module {}".format(
                        c['macaddr'], mi))
            d[mi][c['macaddr']] = c
        cameras = d
    return cameras


def index_configs(db, force=False):
    if table_exists(db, 'configs'):
        if not force:
            logging.warning("table configs already exists, skipping")
            return False
        db.execute("DROP TABLE configs;");
    logging.info("creating configs table")
    db.execute(
        "CREATE TABLE configs ("
        "config_id INTEGER PRIMARY KEY,"
        "camera_id INTEGER,"
        "timestamp TIMESTAMP,"
        "path TEXT"
        ");")

    modules = get_modules()
    cameras = get_cameras(db, by_module_mac=True)
    for module_index in modules:
        module_path = modules[module_index]
        logging.debug(f"indexing module {module_index} at {module_path}")
        camera_config_paths = sorted(
            glob.glob(os.path.join(module_path, 'configs/001f*')))
        for camera_config_path in camera_config_paths:
            logging.debug(f"indexing camera_path {camera_config_path}")
            macaddr = os.path.split(camera_config_path)[-1]
            if macaddr not in cameras[module_index]:
                logging.debug(
                    f"skipping camera {macaddr} in module {module_index} not in info")
                continue
            config_paths = sorted(glob.glob(os.path.join(camera_config_path, '*_*_*')))
            camera_id = cameras[module_index][macaddr]['id']
            for config_path in config_paths:
                rpath = os.path.relpath(config_path, data_dir)
                ts = os.path.split(rpath)[-1]
                dt = datetime.datetime.strptime(ts, '%y%m%d_%H%M%S_%f')
                logging.debug(
                    f"Found config for camera {camera_id} at {dt} in file {rpath}")
                db.execute(
                    "INSERT INTO configs (camera_id, timestamp, path) VALUES (?, ?, ?)",
                    (camera_id, dt, rpath))


def index_detections(db, force=False):
    if table_exists(db, 'detections'):
        if not force:
            logging.warning("table detections already exists, skipping")
            return False
        db.execute("DROP TABLE detections;");
    logging.info("creating detections table")
    db.execute(
        "CREATE TABLE detections ("
        "detection_id INTEGER PRIMARY KEY,"
        "camera_id INTEGER,"
        "timestamp TIMESTAMP,"
        "path TEXT"
        ");")

    modules = get_modules()
    cameras = get_cameras(db, by_module_mac=True)
    for module_index in modules:
        module_path = modules[module_index]
        logging.debug(f"indexing module {module_index} at {module_path}")
        camera_paths = sorted(glob.glob(os.path.join(module_path, 'detections/001f*')))
        for camera_path in camera_paths:
            logging.debug(f"indexing camera_path {camera_path}")
            macaddr = os.path.split(camera_path)[-1]
            if macaddr not in cameras[module_index]:
                logging.debug(
                    f"skipping camera {macaddr} in module {module_index} not in info")
                continue
            detection_paths = sorted(glob.glob(os.path.join(camera_path, '*', '*.json')))
            camera_id = cameras[module_index][macaddr]['id']
            for detection_path in detection_paths:
                rpath = os.path.relpath(detection_path, data_dir)
                ts = '_'.join('_'.join(rpath.split(os.path.sep)[-2:]).split('_')[:-1])
                dt = datetime.datetime.strptime(ts, '%y%m%d_%H%M%S_%f')
                logging.debug(f"Found detection for camera {camera_id} at {dt} in file {rpath}")
                db.execute(
                    "INSERT INTO detections (camera_id, timestamp, path) VALUES (?, ?, ?)",
                    (camera_id, dt, rpath))


def index_videos(db, force=False):
    if table_exists(db, 'videos'):
        if not force:
            logging.warning("table videos already exists, skipping")
            return False
        db.execute("DROP TABLE videos;");
    logging.info("creating videos table")
    db.execute(
        "CREATE TABLE videos ("
        "video_id INTEGER PRIMARY KEY,"
        "camera_id INTEGER,"
        "timestamp TIMESTAMP,"
        "path TEXT"
        ");")

    modules = get_modules()
    cameras = get_cameras(db, by_module_mac=True)
    for module_index in modules:
        module_path = modules[module_index]
        logging.debug(f"indexing module {module_index} at {module_path}")
        camera_paths = sorted(glob.glob(os.path.join(module_path, 'videos/001f*')))
        for camera_path in camera_paths:
            logging.debug(f"indexing camera_path {camera_path}")
            macaddr = os.path.split(camera_path)[-1]
            if macaddr not in cameras[module_index]:
                logging.debug(
                    f"skipping camera {macaddr} in module {module_index} not in info")
                continue
            video_paths = sorted(glob.glob(os.path.join(camera_path, '*', '*.mp4')))
            camera_id = cameras[module_index][macaddr]['id']
            for video_path in video_paths:
                rpath = os.path.relpath(video_path, data_dir)
                ts = '_'.join('_'.join(rpath.split(os.path.sep)[-2:]).split('_')[:-1])
                dt = datetime.datetime.strptime(ts, '%y%m%d_%H%M%S_%f')
                logging.debug(f"Found video for camera {camera_id} at {dt} in file {rpath}")
                db.execute(
                    "INSERT INTO videos (camera_id, timestamp, path) VALUES (?, ?, ?)",
                    (camera_id, dt, rpath))


def index_stills(db, force=False):
    if table_exists(db, 'stills'):
        if not force:
            logging.warning("table stills already exists, skipping")
            return False
        db.execute("DROP TABLE stills;");
    logging.info("creating stills table")
    db.execute(
        "CREATE TABLE stills ("
        "still_id INTEGER PRIMARY KEY,"
        "camera_id INTEGER,"
        "timestamp TIMESTAMP,"
        "path TEXT"
        ");")

    modules = get_modules()
    cameras = get_cameras(db, by_module_mac=True)
    for module_index in modules:
        module_path = modules[module_index]
        logging.debug(f"indexing module {module_index} at {module_path}")
        camera_paths = sorted(glob.glob(os.path.join(module_path, '001f*')))
        for camera_path in camera_paths:
            logging.debug(f"indexing camera_path {camera_path}")
            macaddr = os.path.split(camera_path)[-1]
            if macaddr not in cameras[module_index]:
                logging.debug(
                    f"skipping camera {macaddr} in module {module_index} not in info")
                continue
            still_paths = sorted(glob.glob(os.path.join(camera_path, '*-*-*', 'pic_001', '*.jpg')))
            camera_id = cameras[module_index][macaddr]['id']
            for still_path in still_paths:
                rpath = os.path.relpath(still_path, data_dir)
                ds, _, fn = rpath.split(os.path.sep)[-3:]
                ts = '_'.join((ds, fn.split('[')[0]))
                dt = datetime.datetime.strptime(ts, '%Y-%m-%d_%H.%M.%S')
                if os.path.getsize(still_path) == 0:
                    logging.error(f"0 size still at {rpath}")
                logging.debug(f"Found still for camera {camera_id} at {dt} in file {rpath}")
                db.execute(
                    "INSERT INTO stills (camera_id, timestamp, path) VALUES (?, ?, ?)",
                    (camera_id, dt, rpath))


if __name__ == '__main__':
    with sqlite3.connect(dbfn) as db:
        index_cameras(db, force)
        index_configs(db, force)
        index_detections(db, force)
        index_videos(db, force)
        index_stills(db, force)
        db.commit()
