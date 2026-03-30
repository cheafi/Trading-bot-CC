#!/bin/bash
cd /Users/chantszwai/Projects/TradingAI_Bot
source /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main/venv/bin/activate
nohup python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > /tmp/dashboard.log 2>&1 &
echo "Dashboard launched PID: $!"
sleep 3
echo "Status:"
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:8000/
echo ""
