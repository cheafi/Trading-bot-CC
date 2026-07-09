"""Rule learning loop — agent suggestions without deploy authority."""

from __future__ import annotations

from src.services.rule_learning_loop import (
    RuleRecord,
    apply_alpha_review_to_rules,
    evaluate_rule,
    summarize_rules,
)


def test_noisy_rule_suggested_retire():
    rule = RuleRecord(
        rule_id="r1",
        triggers=10,
        false_alarms=6,
    )
    evaluated = evaluate_rule(rule)
    assert evaluated.status == "noisy"
    assert evaluated.agent_suggestion == "retire"


def test_useful_rule_suggested_promote_review():
    rule = RuleRecord(
        rule_id="r2",
        triggers=12,
        false_alarms=1,
        forward_r_mean=0.7,
    )
    evaluated = evaluate_rule(rule)
    assert evaluated.status == "useful"
    assert evaluated.agent_suggestion == "convert_to_playbook_review"


def test_agent_cannot_deploy_size_handoff():
    summary = summarize_rules(
        [
            {
                "rule_id": "r3",
                "triggers": 15,
                "false_alarms": 2,
                "forward_r_mean": 0.6,
            }
        ]
    )
    assert summary["agent_may_deploy"] is False
    assert summary["agent_may_size"] is False
    assert summary["agent_may_handoff"] is False
    assert summary["authority_effect"] == "none"


def test_alpha_review_thin_evidence_collect_more_samples():
    actions = apply_alpha_review_to_rules(
        rule_summary={
            "rules": [
                {"rule_id": "r4", "triggers": 2, "false_alarms": 0},
            ]
        },
        sample_size=5,
        min_sample=12,
        overfit_pass=False,
    )
    assert actions
    assert actions[0]["agent_suggestion"] == "collect_more_samples"
    assert actions[0]["authority_effect"] == "none"


def test_alpha_review_deteriorating_suggests_tighten():
    actions = apply_alpha_review_to_rules(
        rule_summary={
            "rules": [
                {"rule_id": "r5", "triggers": 8, "false_alarms": 1, "forward_r_mean": 0.2},
            ]
        },
        review_status="deteriorating",
        sample_size=20,
        min_sample=12,
        overfit_pass=True,
        cost_adj_positive=True,
    )
    assert actions[0]["agent_suggestion"] in ("tighten", "keep", "retire", "mute")
    assert actions[0]["may_authorize_deploy"] is False
