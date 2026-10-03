#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
python -m pytest -q
python build_runtime_image.py
python doctor.py
