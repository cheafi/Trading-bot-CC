#!/bin/bash
cd /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main
pkill -9 -f "uvicorn src.api" 2>/dev/null
sleep 2
echo "=== Starting server ==="
exec ./venv/bin/python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
