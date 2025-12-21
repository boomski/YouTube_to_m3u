#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Root dir: $ROOT_DIR"

python3 -m pip install yt-dlp

python3 "$ROOT_DIR/scripts/youtube_m3ugrabber.py" \
  -i "$ROOT_DIR/youtube_channel_info.txt"

echo "m3u grabbed"
