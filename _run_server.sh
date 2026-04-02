#!/bin/bash
cd /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main

# Kill any existing server
kill -9 $(lsof -ti:8000) 2>/dev/null
sleep 1

echo "=== Starting TradingAI Server ==="

# Test import first
./venv/bin/python3 -c "from src.api.main import app; print('Import OK')" 2>&1
if [ $? -ne 0 ]; then
    echo "IMPORT FAILED"
    exit 1
fi

echo "=== Import successful, launching uvicorn ==="

# Start server
exec ./venv/bin/python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
