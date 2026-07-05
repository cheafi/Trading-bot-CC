"""Safe automation — workflow support without gate bypass."""

from src.services.safe_automation_support import (
    build_daily_operator_briefing,
    build_near_miss_auto_recheck,
    build_safe_automation_context,
)


def test_near_miss_recheck_no_deploy():
    nm = [{"ticker": "AAPL", "gaps": ["volume", "rs"]}]
    out = build_near_miss_auto_recheck(nm)
    assert out["may_authorize_deploy"] is False
    assert out["no_auto_deploy"] is True
    for h in out["hints"]:
        assert h["may_authorize_deploy"] is False
        assert h["monitor_only"] is True


def test_daily_briefing_not_board_decision():
    b = build_daily_operator_briefing(tradeability="WAIT", degraded=True)
    assert b["may_authorize_deploy"] is False
    assert b["is_board_decision"] is False
    assert any("degraded" in line.lower() or "core-only" in line.lower() for line in b["sections"][1]["lines"])


def test_safe_automation_envelope():
    ctx = build_safe_automation_context(
        near_miss=[{"ticker": "MSFT", "gaps": ["breadth"]}],
        tradeability="TRADE",
        deployable_count=2,
        ibkr_connected=False,
    )
    assert ctx["may_authorize_deploy"] is False
    assert ctx["no_hidden_authority_escalation"] is True
    assert ctx["near_miss_recheck"]["may_authorize_deploy"] is False
    assert ctx["daily_briefing"]["may_authorize_deploy"] is False
