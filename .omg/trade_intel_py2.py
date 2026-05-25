import re

with open("src/services/trade_review_ai_service.py", "r") as f:
    text = f.read()

# Replace fallback
old_fallback = """    @staticmethod
    def _fallback_review(
        trade: Dict[str, Any], similar_cases: list[Dict[str, Any]]
    ) -> Dict[str, Any]:
        r_multiple = float(trade.get("r_multiple") or 0.0)
        regime = trade.get("regime_at_entry") or "unknown"
        conviction = TradeReviewAIService._conviction(trade)
        verdict = "GOOD_PROCESS" if r_multiple > 0 else "PROCESS_REVIEW"
        what_worked = []
        what_failed = []
        if r_multiple > 0:
            what_worked.append(
                f"{conviction} setup converted to {r_multiple:+.2f}R in {regime}."
            )
        else:
            what_failed.append(
                f"{conviction} setup failed for {r_multiple:+.2f}R in {regime}."
            )
        if float(trade.get("hold_days") or 0) > 0:
            what_worked.append(f"Held for {trade.get('hold_days')} days before exit.")
        if r_multiple < -1:
            what_failed.append(
                "Loss exceeded normal tolerance; check stop discipline and regime gate."
            )
        repeat_rule = (
            "Repeat only when regime matches and R:R is at least 2:1."
            if r_multiple >= 0
            else "Do not repeat unless the same setup has stronger regime alignment and cleaner entry quality."
        )
        similar_case_note = (
            similar_cases[0]["lesson"]
            if similar_cases
            else "No similar memory cases available yet."
        )
        return {
            "verdict": verdict,
            "what_worked": what_worked[:3],
            "what_failed": what_failed[:3],
            "repeat_rule": repeat_rule,
            "confidence_recalibration": (
                "Keep conviction tier unchanged."
                if r_multiple > 0
                else "Downshift conviction by one tier until evidence improves."
            ),
            "similar_case_note": similar_case_note,
        }"""
new_fallback = """    @staticmethod
    def _fallback_review(
        trade: Dict[str, Any], similar_cases: list[Dict[str, Any]]
    ) -> Dict[str, Any]:
        r_multiple = float(trade.get("r_multiple") or 0.0)
        regime = trade.get("regime_at_entry") or "unknown"
        conviction = TradeReviewAIService._conviction(trade)
        verdict = "GOOD_PROCESS" if r_multiple > 0 else "PROCESS_REVIEW"

        # Structured grading (A/B/C/F)
        thesis_quality = "A" if r_multiple > 0 else "C"
        timing_quality = "B" if float(trade.get("hold_days") or 0) > 0 else "F"
        exit_quality = "A" if r_multiple > -1 else "F"
        regime_alignment = "A" if "BULL" in regime.upper() and r_multiple > 0 else "C"

        what_worked = [f"Thesis Quality: {thesis_quality}", f"Regime Alignment: {regime_alignment}"]
        what_failed = [f"Timing Quality: {timing_quality}", f"Exit Quality: {exit_quality}"]
        repeat_rule = "Repeat only when regime matches and R:R is at least 2:1." if r_multiple > 0 else "Do not repeat unless entry timing avoids noise."

        lesson = f"In {regime}, {conviction} setups " + ("have an edge if held patiently." if r_multiple > 0 else "fail when discipline is broken.")

        return {
            "verdict": verdict,
            "what_worked": what_worked,
            "what_failed": what_failed,
            "repeat_rule": repeat_rule,
            "confidence_recalibration": "Keep unchanged." if r_multiple > 0 else "Downshift conviction until evidence improves.",
            "similar_case_note": similar_cases[0]["lesson"] if similar_cases else "No real similar cases to compare against yet.",
            "structured_lesson": lesson
        }"""
text = text.replace(old_fallback, new_fallback)

with open("src/services/trade_review_ai_service.py", "w") as f:
    f.write(text)

print("Replaced fallback_review")
