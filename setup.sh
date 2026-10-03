#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .grader-system-venv
.grader-system-venv/bin/python -m pip install --upgrade pip
.grader-system-venv/bin/pip install -r requirements.txt
.grader-system-venv/bin/python build_runtime_image.py
echo "Grader environment and student runtime image are ready."
echo "Export OPENAI_API_KEY before automatic AI plan resolution."
