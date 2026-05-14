"""
Loaded/saved by camera name (ip)
Working copy in /dev/shm (for interaction with UI/running grabber)
Non-volitile copy in ~/.pcam/ (load if no working copy, save manually)

Config should contain
- trigger mask & other settings
- roi(s)
- data directory: /mnt/data/
- return of last service check (so UI doesn't have to poll service)

Steal some config code from discover.py
Might also be used for discovery with
- ips of known cameras and not cameras
- service statuses
- likely cameras (that aren't configured)
"""

import json
import logging
import os
import shutil


static_cfg_dir = os.path.expanduser('~/.pcam/')
working_cfg_dir = '/dev/shm/pcam/'  # should be on a tmpfs
thumbnail_dir = '/dev/shm/pcam_thumbnails/'


for d in (thumbnail_dir, ):
    if not os.path.exists(d):
        os.makedirs(d)


class ConfigLoadError(Exception):
    pass


def get_modified_time(name):
    fn = os.path.join(working_cfg_dir, name)
    if not os.path.exists(fn):
        return None
    return os.path.getmtime(fn)


def load_config(name, default=None):
    logging.debug("Loading config: %s", name)
    sfn = os.path.join(static_cfg_dir, name)
    wfn = os.path.join(working_cfg_dir, name)
    if not os.path.exists(wfn):
        logging.debug("load_config: no working file file: %s", wfn)
        if not os.path.exists(sfn):
            # no static file, return default value
            logging.debug("load_config: returning default value")
            return default
        else:  # static file exists, no working file
            # copy static file to working file
            logging.debug("load_config: copy static file %s to %s", sfn, wfn)
            shutil.copy(sfn, wfn)
            # for now read the static file
            fn = sfn
    else: # a working file exists, use it
        logging.debug("load_config: loading working file: %s", wfn)
        fn = wfn
    with open(fn, 'r') as f:
        return json.load(f)


def save_config(config, name, static=False):
    if static:
        fn = os.path.join(static_cfg_dir, name)
    else:
        fn = os.path.join(working_cfg_dir, name)
    fn = os.path.expanduser(fn)
    dn = os.path.dirname(fn)
    logging.debug("Saving config to: %s", fn)
    if not os.path.exists(dn):
        logging.debug("Making directory for config: %s", fn)
        os.makedirs(dn)
    with open(fn, 'w') as f:
        json.dump(config, f)
