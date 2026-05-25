#!/bin/bash
cd "$(dirname "$0")"
nohup ./venv/bin/python3 _cc_instant.py > /tmp/cc_server.log 2>&1 &
echo "PID=$!"
sleep 3
cat /tmp/cc_server.log
