import datetime
import sqlite3


db = sqlite3.connect('pcam.sqlite', detect_types=sqlite3.PARSE_DECLTYPES)

# count camera/module pairs
cameras = [r for r in db.execute("SELECT camera_id, mac, module, start, end FROM cameras").fetchall()]
print("{} camera/modules pairs".format(len(cameras)))

# count unique macaddrs
macaddrs = set([r[1] for r in cameras])
print("{} unique camera mac addresses".format(len(macaddrs)))


def get_timestamps(table, camera_id, start, end):
    return [
        r[0] for r in
        db.execute(
            f"SELECT timestamp FROM {table} WHERE camera_id=? AND timestamp>=? AND timestamp<=?",
            (camera_id, start, end)).fetchall()]


def plot_timestamps(ts, max_value=None, delta=None, start_time=None):
    if len(ts) == 0:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    nchars = len(chars)
    to_char = lambda f: chars[max(0, min(nchars - 1, int(f * (nchars - 1) + 0.5)))]

    # count per day
    if delta is None:
        td = datetime.timedelta(days=1)
    else:
        td = delta
    if start_time is None:
        st = ts[0]
    else:
        st = start_time
    nt = st + td
    day_counts = [0]
    for t in ts[1:]:
        if t < nt:
            day_counts[-1] += 1
        else:
            while t >= nt:
                st = nt
                nt = st + td
                day_counts.append(0)

    # max per day
    if max_value is None:
        max_value = max(day_counts)
    if max_value == 0:
        return " " * len(day_counts)
    return "".join([to_char(n / max_value) for n in day_counts])


def format_breaks(still_blocks):
    st = still_blocks[0][0]
    et = still_blocks[-1][1]
    days = (et - st).days

    bi = 0
    #b = still_blocks[0]
    td = datetime.timedelta(days=1)
    cursor = st
    s = ''
    while cursor < et:
        l, r = cursor, cursor + td
        if bi < len(still_blocks):
            bl, br = still_blocks[bi]
            if l >= bl and r <= br:  # in block
                s += '*'
            elif l > br:  # off end of block, check next block
                bi += 1
                continue
            elif r < bl:  # not yet at next block, missing data
                s += ' '
            else:  # partial
                s += '-'
        cursor = r
    return s


# for each camera/module pair
camera_data = {}
for camera in cameras:
    # print out module, macaddr, id
    camera_id, mac, module_id, start, end = camera
    print(
        f"Camera {camera_id}, mac={mac}, module={module_id}, start={start}, end={end}")

    config_timestamps = get_timestamps('configs', camera_id, start, end)
    detection_timestamps = get_timestamps('detections', camera_id, start, end)
    video_timestamps = get_timestamps('videos', camera_id, start, end)
    still_timestamps = get_timestamps('stills', camera_id, start, end)

    if len(still_timestamps) < 1000:
        print("\t skipping {} < 1000 stills".format(len(still_timestamps)))
        continue

    start_time = still_timestamps[0]
    end_time = still_timestamps[-1]
    for ts in (video_timestamps, detection_timestamps, config_timestamps):
        if len(ts) == 0:
            continue
        start_time = min(start_time, ts[0])
        end_time = max(end_time, ts[-1])
    delta_time = end_time - start_time
    print("\t{} config changes".format(len(config_timestamps)))
    print("\t\t{}".format(plot_timestamps(
        config_timestamps, start_time=start_time)))
    print("\t{} detection events".format(len(detection_timestamps)))
    print("\t\t{}".format(plot_timestamps(
        detection_timestamps, start_time=start_time)))
    print("\t{} videos".format(len(video_timestamps)))
    print("\t\t{}".format(plot_timestamps(
        video_timestamps, start_time=start_time)))
    print("\t{} stills".format(len(still_timestamps)))
    print("\t\t{}".format(plot_timestamps(
        still_timestamps, max_value=24 * 60, start_time=start_time)))
    print("\t{} duration of recording".format(delta_time))
    camera_data[camera_id] = {
        'mac': mac,
        'module': module_id,
        'configs': config_timestamps,
        'detections': detection_timestamps,
        'videos': video_timestamps,
        'stills': still_timestamps,
    }

print("------")
print("Total data")
n_stills = sum([len(camera_data[cid]['stills']) for cid in camera_data])
n_detections = sum([len(camera_data[cid]['detections']) for cid in camera_data])
n_videos = sum([len(camera_data[cid]['videos']) for cid in camera_data])
print(f"\t{n_stills} stills")
print(f"\t{n_detections} detections")
print(f"\t{n_videos} videos")
