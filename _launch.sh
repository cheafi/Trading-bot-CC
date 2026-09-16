#!/bin/bash
cd "$(dirname "$0")"
mkdir -p data/state
nohup ./venv/bin/python3 _cc_instant.py > data/state/cc_server.log 2>&1 &
echo "PID=$!"
sleep 3
cat data/state/cc_server.log
