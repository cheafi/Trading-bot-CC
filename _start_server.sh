#!/bin/bash
# Kill old processes
kill $(lsof -ti:8000) 2>/dev/null
kill $(lsof -ti:8001) 2>/dev/null
sleep 1

cd /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main
nohup venv/bin/python3 _cc_instant.py > /tmp/cc_server.log 2>&1 &
echo "PID=$!"
sleep 5
curl -s http://localhost:8000/health
echo ""
