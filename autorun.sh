#!/bin/bash

echo $(dirname $0)

python3 -m pip install yt-dlp

python scripts/youtube_m3ugrabber.py -i ../youtube_channel_info.txt

echo m3u grabbed
