"""
Credential loading for PCAM_USER and PCAM_PASSWORD.

Priority order:
  1. ~/.config/autopolls/credentials  (written by autopolls-install)
  2. PCAM_USER / PCAM_PASSWORD environment variables  (legacy / override)

The credentials file uses env-file format (KEY=value, one per line) so it
can also be loaded directly by systemd via EnvironmentFile=.
"""

import os
from pathlib import Path

CREDS_PATH = Path.home() / '.config' / 'autopolls' / 'credentials'


def _load_file():
    if not CREDS_PATH.exists():
        return {}
    result = {}
    for line in CREDS_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, val = line.partition('=')
            result[key.strip()] = val.strip()
    return result


def get_user() -> str:
    return _load_file().get('PCAM_USER') or os.environ.get('PCAM_USER', '')


def get_password() -> str:
    return _load_file().get('PCAM_PASSWORD') or os.environ.get('PCAM_PASSWORD', '')
