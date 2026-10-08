#!/bin/bash
cd "$(dirname "$0")"
pkill -f "python -m photo_tidy" 2>/dev/null
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
exec .venv/bin/python -m photo_tidy "$@"
