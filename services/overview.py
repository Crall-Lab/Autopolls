
import datetime
import os
import subprocess


ddir = '/mnt/data'
odir = os.path.join(ddir, 'overviews')
delta_hours = -24
cmd_string = (
    "ffmpeg -framerate 30 -f image2 -pattern_type glob -i '*.jpg' "
    "-vf scale=640:-1 -codec h264_omx -profile:v high -b:v 3200k "
    "{output_filename}")


def is_name(n):
    if len(n) != 12:
        return False
    try:
        int(n, 16)  # is hex
        return True
    except ValueError:
        return False
    return False


# for yesterday
td = datetime.timedelta(hours=delta_hours)
dt = datetime.datetime.now() + td
ts = dt.strftime('%Y-%m-%d')
print("Processing overviews for %s" % ts)
names = [n for n in os.listdir(ddir) if is_name(n)]
results = {}
for n in names:
    idir = os.path.join(ddir, n, ts, 'pic_001')
    if not os.path.exists(idir):
        print("No images for %s, skipping" % n)
        continue

    # make output filename
    fn = os.path.join(odir, n, '%s_%s.mp4' % (n, ts))
    dn = os.path.dirname(fn)
    if not os.path.exists(dn):
        os.makedirs(dn)
    print("Generating %s" % fn)
    cmd = cmd_string.format(output_filename=fn)
    # run in shell and cmd not as list to allow wildcard
    r = subprocess.run(cmd, cwd=idir, shell=True)
    print("Overview finished with %s" % r.returncode)
    results[n] = r.returncode

print("Overview generation finished")
for n in results:
    print("\t%s: %s" % (n, results[n]))
