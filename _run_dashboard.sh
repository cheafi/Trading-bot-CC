#!/bin/bash
cd /Users/chantszwai/Projects/TradingAI_Bot
source /Users/chantszwai/Documents/GitHub/TradingAI_Bot-main/venv/bin/activate
exec python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
