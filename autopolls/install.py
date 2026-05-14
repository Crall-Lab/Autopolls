"""
autopolls-install  — system setup for the Autopolls pollinator monitoring system.
autopolls-config   — launch the config file GUI editor.

autopolls-install must be run with sudo so it can write to /etc/systemd/system/
and /etc/nginx/sites-enabled/.  It reads the *invoking* user from SUDO_USER so
that paths and the credentials file are resolved for the actual human account.
"""

import getpass
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths derived from the package layout
# ---------------------------------------------------------------------------

REPO_ROOT    = Path(__file__).parent.parent         # Autopolls/
PCAM_DIR     = REPO_ROOT / 'pcam'                   # Autopolls/pcam/
SERVICES_DIR = PCAM_DIR / 'services'                # Autopolls/pcam/services/
UTILS_DIR    = REPO_ROOT / 'utils'                  # Autopolls/utils/

APT_DEPS = [
    'python3-gst-1.0',
    'python3-systemd',
    'libedgetpu1-std',
    'nginx-full',
    'vsftpd',
    'apache2-utils',
    'nmap',
    'jq',
    'libsystemd-dev',
]

SERVICES_TO_WRITE = [
    'tfliteserve.service',
    'pcam-discover.service',
    'pcam-overview.service',
    'pcam-overview.timer',
    'pcam@.service',
    'pcam-ui.service',
]

SERVICES_TO_ENABLE = [
    'tfliteserve.service',
    'pcam-discover.service',
    'pcam-overview.timer',
    'pcam-ui.service',
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(text):
    print(f'\n\033[1;32m==> {text}\033[0m')


def _print_ok(text):
    print(f'    \033[32m✓\033[0m {text}')


def _print_warn(text):
    print(f'    \033[33m!\033[0m {text}')


def _print_step(text):
    print(f'    {text}')


def _run(cmd, check=True, **kwargs):
    return subprocess.run(cmd, check=check, **kwargs)


def _get_install_user():
    """Return (username, home_path) of the human who invoked sudo."""
    sudo_user = os.environ.get('SUDO_USER')
    if sudo_user:
        pw = pwd.getpwnam(sudo_user)
        return pw.pw_name, Path(pw.pw_dir)
    pw = pwd.getpwuid(os.getuid())
    return pw.pw_name, Path(pw.pw_dir)


def _get_venv_bin():
    """Return the bin/ directory of the active virtualenv."""
    return Path(sys.executable).parent


def _render_service(template_path: Path, replacements: dict) -> str:
    text = template_path.read_text()
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


# ---------------------------------------------------------------------------
# Install steps
# ---------------------------------------------------------------------------

def check_apt_deps():
    _print_header('Checking apt dependencies')
    missing = []
    for pkg in APT_DEPS:
        result = _run(['dpkg', '-l', pkg], check=False, capture_output=True)
        if result.returncode != 0:
            missing.append(pkg)
    if missing:
        _print_warn('The following apt packages are missing:')
        print()
        print(f'    sudo apt install {" ".join(missing)}')
        print()
        _print_warn('Install them and re-run autopolls-install.')
        sys.exit(1)
    _print_ok('All apt dependencies present')


def setup_credentials(user_home: Path, username: str):
    """Prompt for camera credentials and write to ~/.config/autopolls/credentials."""
    _print_header('Camera credentials')

    creds_dir  = user_home / '.config' / 'autopolls'
    creds_path = creds_dir / 'credentials'

    if creds_path.exists():
        answer = input(
            f'    Credentials already exist at {creds_path}.\n'
            '    Update them? [y/N] '
        ).strip().lower()
        if answer != 'y':
            _print_ok('Keeping existing credentials')
            return _read_credentials(creds_path)

    print(
        '\n    These credentials are used to authenticate with Dahua IP cameras\n'
        '    and to protect the web UI.\n'
    )

    cam_user = input('    Camera username: ').strip()
    while True:
        cam_pass  = getpass.getpass('    Camera password: ')
        cam_pass2 = getpass.getpass('    Confirm password: ')
        if cam_pass == cam_pass2:
            break
        print('    Passwords do not match, try again.')

    creds_dir.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(
        f'PCAM_USER={cam_user}\n'
        f'PCAM_PASSWORD={cam_pass}\n'
    )
    # Owned by the real user, readable only by them
    uid = pwd.getpwnam(username).pw_uid
    os.chown(creds_path, uid, -1)
    creds_path.chmod(0o600)

    _print_ok(f'Credentials written to {creds_path}')
    return cam_user, cam_pass


def _read_credentials(creds_path: Path):
    result = {}
    for line in creds_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, _, v = line.partition('=')
            result[k.strip()] = v.strip()
    return result.get('PCAM_USER', ''), result.get('PCAM_PASSWORD', '')


def copy_default_config(user_home: Path):
    _print_header('Config file')
    dest = user_home / 'Desktop' / 'configs'
    src  = UTILS_DIR / 'configs'
    if dest.exists():
        _print_ok(f'Config already exists at {dest} — not overwriting')
    elif not src.exists():
        _print_warn(f'Default config not found at {src} — skipping')
    else:
        shutil.copy2(src, dest)
        dest.chmod(0o666)
        _print_ok(f'Copied default config to {dest}')
    _print_step(f'Edit with:  autopolls-config  (or open {dest})')


def install_services(username: str, user_home: Path, venv_bin: Path):
    _print_header('Installing systemd service files')

    creds_path = user_home / '.config' / 'autopolls' / 'credentials'
    replacements = {
        '@@INSTALL_USER@@': username,
        '@@VENV_BIN@@':     str(venv_bin),
        '@@PCAM_DIR@@':     str(PCAM_DIR),
        '@@CREDS_PATH@@':   str(creds_path),
    }

    systemd_dir = Path('/etc/systemd/system')
    for svc_name in SERVICES_TO_WRITE:
        template = SERVICES_DIR / svc_name
        if not template.exists():
            _print_warn(f'{svc_name} not found in {SERVICES_DIR}, skipping')
            continue
        dest = systemd_dir / svc_name
        dest.write_text(_render_service(template, replacements))
        _print_ok(f'Wrote {dest}')

    _run(['systemctl', 'daemon-reload'])
    _print_ok('systemctl daemon-reload done')


def enable_services():
    _print_header('Enabling services')
    for svc in SERVICES_TO_ENABLE:
        _run(['systemctl', 'enable', svc], check=False)
        _print_ok(f'Enabled {svc}')


def setup_nginx():
    _print_header('Configuring nginx')
    nginx_src  = SERVICES_DIR / 'pcam-ui.nginx'
    nginx_dest = Path('/etc/nginx/sites-enabled/pcam-ui')
    default    = Path('/etc/nginx/sites-enabled/default')

    if default.exists():
        default.unlink()
        _print_ok('Removed default nginx site')

    if nginx_dest.exists() or nginx_dest.is_symlink():
        nginx_dest.unlink()
    nginx_dest.symlink_to(nginx_src)
    _print_ok(f'Linked {nginx_src} → {nginx_dest}')
    _run(['systemctl', 'restart', 'nginx'], check=False)
    _print_ok('nginx restarted')


def setup_htpasswd(password: str):
    _print_header('Web UI password')
    if not password:
        _print_warn('No password provided — skipping htpasswd setup')
        _print_step('Run manually: sudo htpasswd -bc /etc/apache2/.htpasswd pcam <password>')
        return
    htpasswd = Path('/etc/apache2/.htpasswd')
    htpasswd.parent.mkdir(parents=True, exist_ok=True)
    _run(['htpasswd', '-bc', str(htpasswd), 'pcam', password])
    _print_ok('htpasswd configured')


def print_manual_steps():
    _print_header('Remaining manual steps')
    steps = [
        '1. Set up external storage (/dev/sda1 → /mnt/data):',
        '      See "Setup storage location" in README.md',
        '',
        '2. (Optional) MCC134 thermocouple board:',
        '      See "Install MCC134" in README.md',
        '',
        '3. (Optional) wittyPi power scheduler:',
        '      See "Install wittyPi" in README.md',
        '',
        '4. Start services:',
        '      sudo systemctl start tfliteserve.service pcam-discover.service pcam-ui.service',
        '',
        '5. Open the web UI at http://127.0.0.1 (Pi browser) or http://<pi-ip> (remote)',
    ]
    for s in steps:
        print(f'    {s}')
    print()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def main():
    if os.geteuid() != 0:
        print('autopolls-install must be run with sudo:', file=sys.stderr)
        print('  sudo autopolls-install', file=sys.stderr)
        sys.exit(1)

    username, user_home = _get_install_user()
    venv_bin = _get_venv_bin()

    print(f'\nAutopolls installer')
    print(f'  User:     {username}  ({user_home})')
    print(f'  Venv bin: {venv_bin}')
    print(f'  Repo:     {REPO_ROOT}')

    check_apt_deps()
    _, password = setup_credentials(user_home, username)
    copy_default_config(user_home)
    install_services(username, user_home, venv_bin)
    enable_services()
    setup_nginx()
    setup_htpasswd(password)
    print_manual_steps()

    print('\033[1;32m\nInstall complete.\033[0m\n')


def config_main():
    """Launch the config file GUI editor."""
    config_editor = UTILS_DIR / 'config_editor.py'
    if not config_editor.exists():
        print(f'Config editor not found at {config_editor}', file=sys.stderr)
        sys.exit(1)
    os.execv(sys.executable, [sys.executable, str(config_editor)] + sys.argv[1:])
