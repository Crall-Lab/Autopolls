"""
Flask won't serve up /mnt/data nicely (no dir listing)
So use apache or nginx etc to serve

Functions
- camera status
  - name & ip
  - systemd service status and up time
  - recording state (can I get this?)
  - link to open in vlc [make from ip & PCAM_* env vars]
  - link to most recent snapshot
  - link to data for yesterday & today [requires static file serving]
- system status
  - disk space
  - temperature
  - weather...
"""

import datetime
import glob
import io
import os
import shutil

import flask

from . import config
from . import discover
from . import grabber


this_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
app = flask.Flask(
    'pcam', static_folder=os.path.join(this_dir, 'static'))


thumbnail_cache = {}


@app.route("/", methods=["GET"])
def index():
    # TODO fix this, make it a relative path
    path = os.path.join(this_dir, 'static', 'index.html')
    return flask.send_file(path, mimetype='text/html')


@app.route("/temperature", methods=["GET"])
def temperature():
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
        return flask.jsonify(int(f.read().strip()) / 1000.)


@app.route("/disk_usage", methods=["GET"])
def disk_info():
    du = shutil.disk_usage(grabber.data_dir)
    return flask.jsonify({
        'total': du.total,
        'used': du.used,
        'free': du.free,
    })


@app.route("/freeze", methods=["POST"])
def freeze_camera_configs():
    # write all camera configs to static directory
    cnames = list(discover.get_cameras().values())
    for name in cnames:
        cfg = config.load_config(name, None)
        if cfg is None:
            continue
        config.save_config(cfg, name, static=True)
    return flask.make_response(flask.jsonify(cnames), 200)


@app.route("/cfg", methods=["GET", "POST"])
@app.route("/cfg/<name>", methods=["GET", "POST"])
def camera_config(name=None):
    if name is None:  # get/set all
        cnames = list(discover.get_cameras().values())
    if flask.request.method == 'GET':  # return config
        if name is None:  # get/set all
            return flask.jsonify({
                cname: config.load_config(cname)
                for cname in cnames})
        return flask.jsonify(config.load_config(name))
    if flask.request.method == 'POST':  # update config
        if not flask.request.json:
            flask.abort(400)
        # TODO verify config
        cfg = flask.request.json
        if name is None:  # update all cameras
            [config.save_config(cfg, cname) for cname in cnames]
        else:  # update 1 camera
            config.save_config(cfg, name)
        return flask.make_response(flask.jsonify(None), 200)


@app.route("/cameras", methods=["GET"])
@app.route("/cameras/", methods=["GET"])
@app.route("/cameras/<date>", methods=["GET"])
def camera_list(date=None):
    if date is None:
        date = datetime.datetime.now()
        day = date.strftime('%Y-%m-%d')
    else:
        day = date
        try:
            date = datetime.datetime.fromisoformat(date)
        except ValueError:
            return flask.abort(400)

    ts = date.strftime('%y%m%d')

    # load config key=ip, value=name [or False if not a camera]
    #cfg = discover.load_cascaded_config()
    #ips_to_names = {k: cfg[k] for k in cfg if isinstance(cfg[k], str)}

    # get systemd status and uptime of all ips
    #service_states = discover.status_of_all_camera_services()

    detections_path = os.path.join(grabber.data_dir, 'detections')

    # load last 'discover' result
    cfg = config.load_config(discover.cfg_name, {})
    
    cams = []
    #for ip in ips_to_names:
    for ip in cfg:
        if not cfg[ip]['is_camera'] or not cfg[ip]['is_configured']:
            continue
        #s = service_states.get(ip, {})
        s = cfg[ip]['service']
        #name = ips_to_names[ip]
        name = cfg[ip]['name']
        detections = sorted(glob.glob(os.path.join(
            detections_path,
            name,
            ts,
            '*',
        )))
        cams.append({
            'day': day,
            'ip': ip,
            'name': name,
            'active': s.get('Active', False),
            'uptime': s.get('Uptime', -1),
            'detections': detections,
            'cfg': config.load_config(name),
        })
    cams.sort(key=lambda c: c['name'])
    return flask.jsonify(cams)


@app.route("/snapshot/<name>", methods=["GET"])
@app.route("/snapshot/<name>/", methods=["GET"])
@app.route("/snapshot/<name>/<date>", methods=["GET"])
def snapshot(name, date=None):
    most_recent = True
    if date is None:
        date = datetime.datetime.now()
    else:
        # if no ':' in date, no minute was defined
        most_recent &= ':' not in date
        try:
            date = datetime.datetime.fromisoformat(date)
        except ValueError:
            return flask.abort(400)
        # if date was today, grab most recent
        most_recent &= date.date() == datetime.datetime.now().date()

    # is a thumbnail available?
    fn = os.path.join(config.thumbnail_dir, name + '.jpg')
    if name in thumbnail_cache or os.path.exists(fn):
        # TODO how to go back in time for stills
        if os.path.exists(fn):
            with open(fn, 'rb') as f:
            # cache this to always use thumbnails
                im = io.BytesIO(f.read())
            thumbnail_cache[name] = im
            # delete thumbnail to get a new one
            os.remove(fn)
        return flask.send_file(
            thumbnail_cache[name],
            mimetype='image/jpg')
    else:
        # get most recent day
        path = os.path.join(
            grabber.data_dir,
            name,
            date.strftime('%Y-%m-%d'),
            'pic_001')
        if most_recent:
            fn_glob = os.path.join(path, '*.jpg')
        else:
            fn_glob = os.path.join(path, date.strftime('%H.%M') + '*.jpg')
        fns = sorted(glob.glob(fn_glob))
    if len(fns) == 0:
        return flask.abort(404)
    return flask.send_file(fns[-1], mimetype='image/jpg')


def run_ui(**kwargs):
    kwargs['host'] = kwargs.get('host', '0.0.0.0')
    kwargs['port'] = kwargs.get('port', 5000)
    print("Running on %s:%i" % (kwargs['host'], kwargs['port']))
    #app.config["DEBUG"] = True
    #app.debug = True
    app.run(**kwargs)


def cmdline_run():
    run_ui()
