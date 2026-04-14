#!/bin/bash
cd /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main
exec /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main/venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
