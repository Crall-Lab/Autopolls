"""
Python entry point that replaces run_tfliteserve.sh.
Reads the config file to pick the right model and starts the server.
"""

import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / 'Desktop' / 'configs'

# Root of the tfliteserve directory (where model subdirectories live)
MODELS_DIR = Path(__file__).parent.parent

# Map (classes, coral) → (model path, labels path) relative to MODELS_DIR
MODEL_MAP = {
    ('single', False): (
        'autopolls_od_v11_2026/yolov11n_beedetector.tflite',
        'autopolls_od_v11_2026/labels.txt',
    ),
    ('single', True): (
        'autopolls_od_v11_2026/yolov11n_beedetector.tflite',
        'autopolls_od_v11_2026/labels.txt',
    ),
    ('multi', False): (
        'tflite_20220630_1/model.tflite',
        'tflite_20220630_1/labels.txt',
    ),
    ('multi', True): (
        'tflite_20220630_1/model.tflite',
        'tflite_20220630_1/labels.txt',
    ),
}


def run():
    """tfliteserve-server: reads config and starts the inference server."""
    from . import cmdline

    cfg = {}
    if CONFIG_PATH.is_file():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)

    classes = cfg.get('classes', 'single')
    coral   = bool(cfg.get('coral', 0))

    model_rel, labels_rel = MODEL_MAP.get(
        (classes, coral), MODEL_MAP[('single', False)]
    )
    model_path  = MODELS_DIR / model_rel
    labels_path = MODELS_DIR / labels_rel

    if not model_path.exists():
        print(
            f'Model not found: {model_path}\n'
            'Check your config "classes" value and that model files are present.',
            file=sys.stderr,
        )
        sys.exit(1)

    sys.argv = [
        sys.argv[0],
        '-m', str(model_path),
        '-l', str(labels_path),
        '-j', '-1',
        '-T', 'detector',
    ]
    if coral:
        sys.argv.append('-e')

    cmdline.run_server()
