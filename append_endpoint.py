import os

with open("src/api/routers/decision.py", "r", encoding="utf-8") as f:
    text = f.read()

new_endpoint = """

@router.post("/api/v7/today/ai-narrative")
async def generate_today_ai_narrative(payload: dict):
    \"\"\"Standalone AI narrative decoupled from the hot path.\"\"\"
    try:
        from src.services.ai_service import get_ai_service
        ai = get_ai_service()
        if not ai.is_configured:
            return {"ai_narrative": None}
            
        regime_ctx = payload.get("regime_ctx", {})
        top5 = payload.get("top_5", [])
        market_pulse = payload.get("market_pulse", {})
        funnel = payload.get("filter_funnel", {})
        
        narrative = await ai.generate_narrative(regime_ctx, top5, market_pulse, funnel)
        return {"ai_narrative": narrative}
    except Exception as exc:
        return {"ai_narrative": f"Error: {exc}"}
"""

if "/api/v7/today/ai-narrative" not in text:
    with open("src/api/routers/decision.py", "a", encoding="utf-8") as f:
        f.write(new_endpoint)
