"""
Python entry points that replace run_pcam.sh and run_discover.sh.
These read the config file to determine runtime flags so the service
files can point directly to installed scripts without shell wrappers.
"""

import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / 'Desktop' / 'configs'


def _load_config():
    if CONFIG_PATH.is_file():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def run():
    """pcam-run: reads model_inference from config, then runs the grabber."""
    from . import grabber

    cfg = _load_config()
    model_inference = cfg.get('model_inference', 1)

    # Preserve any extra arguments passed to the entry point (e.g. camera IP
    # from the systemd %i specifier: ExecStart=pcam-run %i)
    extra = sys.argv[1:]

    flags = ['-c', '-D', '-r', '-t', '-v']
    if not model_inference:
        flags.append('-f')

    if extra:
        flags += ['-l', extra[0]] + extra[1:]

    sys.argv = [sys.argv[0]] + flags
    grabber.cmdline_run()


def run_discover():
    """pcam-discover: starts the camera discovery service."""
    from . import discover
    discover.cmdline_run()
