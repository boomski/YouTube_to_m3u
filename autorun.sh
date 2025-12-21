#!/bin/bash

echo $(dirname $0)

python3 -m pip install yt-dlp
cd $(dirname $0)/scripts/

python youtube_m3ugrabber.py -i youtube_channel_info.txt

echo m3u grabbed
