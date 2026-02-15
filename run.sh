#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export LC_NUMERIC=C
python src/main.py "$@"
