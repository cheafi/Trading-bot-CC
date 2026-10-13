"""Unit tests for best_action service (fixtures are SYNTHETIC)."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from src.services.best_action import (
    build_best_action,
    compute_theme_overlap,
    enrich_ranked_payload,
)


def _synthetic_trade():
    """SYNTHETIC TRADE conviction, R:R 3:1; never overrides a WAIT gate."""
    return {
        "ticker": "QCOM",
        "action": "TRADE",
        "final_conf": 0.72,
        "entry_price": 180,
        "stop_price": 170,
        "target_price": 210,
        "risk_reward": 3.0,
        "execution_ready": True,
        "score": 8.5,
        "thesis_conf": 0.75,
        "timing_conf": 0.75,
        "exec_conf": 0.75,
        "data_conf": 0.75,
        "evidence_badge": "SYNTHETIC",
    }


class TestBestAction(unittest.TestCase):
    def test_build_best_action_picks_trade_and_watch(self):
        opps = [
            {
                "ticker": "QCOM",
                "action": "TRADE",
                "final_conf": 0.72,
                "entry_price": 180,
                "stop_price": 170,
                "execution_ready": True,
            },
            {
                "ticker": "AMD",
                "action": "WATCH",
                "final_conf": 0.55,
                "upgrade_trigger": "Reclaim $165 on volume",
            },
        ]
        ba = build_best_action(
            opps,
            tradeability="SELECTIVE",
            should_trade=True,
            ibkr_connected=True,
            ibkr_mode="paper",
        )
        self.assertEqual(ba["best_trade_now"]["ticker"], "QCOM")
        self.assertEqual(ba["best_watch_upgrade"]["ticker"], "AMD")
        self.assertTrue(ba["execution_readiness"]["bracket_ready"])

    def test_overlap_warns_semi_cluster(self):
        opps = [
            {"ticker": t, "sector_type": "HIGH_GROWTH"}
            for t in ("NVDA", "AMD", "AVGO", "AMAT", "LRCX")
        ]
        ow = compute_theme_overlap(opps)
        self.assertGreaterEqual(ow["semi_count"], 4)
        self.assertTrue(ow["warnings"])

    def test_enrich_ranked_payload(self):
        payload = enrich_ranked_payload(
            {
                "opportunities": [
                    {"ticker": "SPY", "action": "WATCH", "final_conf": 0.5}
                ],
                "stale": False,
                "source": "test",
            }
        )
        self.assertIn("best_action", payload)
        self.assertIn("overlap_warning", payload)


def test_enrich_ranked_payload_respects_board_wait_gate():
    payload = enrich_ranked_payload(
        {
            "opportunities": [_synthetic_trade()],
            "stale": False,
            "source": "test",
            "tradeability": "WAIT",
            "cc_state": {
                "tradeability_state": {"tradeability": "WAIT", "should_trade": False}
            },
        }
    )
    ba = payload["best_action"]
    assert payload["decision_authority"]["gates"]["regime_wait"] is True
    assert payload["decision_authority"]["allows_trade_labels"] is False
    assert ba["capital_stance"] == "hold_cash"
    assert ba["best_trade_now"] is None
    assert ba["execution_readiness"]["can_send_order"] is False
    assert payload["opportunities"][0]["effective_action"] != "TRADE"


class TestFailClosedBestAction(unittest.TestCase):
    def setUp(self):
        # No broker calls or ranker side effects: all external inputs SYNTHETIC.
        self.readiness = self.enterContext(
            patch(
                "src.services.execution_readiness.build_execution_readiness",
                side_effect=lambda **kwargs: {"trade_handoff_ready": True},
            )
        )
        self.enterContext(
            patch(
                "src.services.ibkr_service.ibkr_authority_gate_snapshot",
                return_value={"connected": True, "circuit_breaker": False},
            )
        )
        self.enterContext(
            patch(
                "src.services.ibkr_service.get_ibkr_service",
                return_value=SimpleNamespace(_mode="paper"),
            )
        )
        self.ranker = self.enterContext(
            patch(
                "src.services.cost_adjusted_ranker.enrich_opportunity_rows",
                side_effect=lambda rows, **kwargs: [dict(row) for row in rows],
            )
        )

    def enrich(self, **overrides):
        return enrich_ranked_payload(
            {
                "opportunities": [_synthetic_trade()],
                "tradeability": "TRADE",
                "source": "test",
                **overrides,
            }
        )

    def assert_denied(self, payload):
        authority = payload["decision_authority"]
        summary = payload["best_action"]
        self.assertFalse(authority["allows_trade_labels"])
        self.assertNotEqual(authority["effective_action_max"], "DEPLOY")
        self.assertEqual(summary["capital_stance"], "hold_cash")
        self.assertIsNone(summary["best_trade_now"])
        self.assertIsNone(summary["best_pilot_now"])
        self.assertEqual(summary["execution_ready_count"], 0)
        self.assertFalse(summary["execution_readiness"]["can_send_order"])
        self.assertEqual(authority["deploy_ideas_count"], 0)
        for key in ("opportunities", "near_miss", "near_miss_rows"):
            for row in payload.get(key) or []:
                self.assertNotIn(row["action"], ("TRADE", "PILOT"))
                self.assertNotIn(row["effective_action"], ("TRADE", "PILOT"))
                self.assertNotIn(
                    row["pilot_state"], ("FULL_DEPLOY", "PILOT_EXECUTABLE")
                )
                self.assertFalse(row["execution_ready"])
                self.assertFalse(row["decision_authority"]["allows_trade_labels"])
        for bucket in payload["bucket_quality"]:
            self.assertTrue(bucket["deploy_line"].startswith("0/"))
        self.assertEqual(summary["trade_count"], 0)

    def test_nested_board_veto_precedes_top_level_trade(self):
        for state in (
            {"tradeability": "WAIT"},
            {"tradeability": "NO_TRADE"},
            {"tradeability": "TRADE", "deploy_blocked": True},
            {"tradeability": "TRADE", "should_trade": False},
        ):
            with self.subTest(state=state):
                payload = self.enrich(cc_state={"tradeability_state": state})
                self.assert_denied(payload)
                self.assertTrue(payload["decision_authority"]["gates"]["regime_wait"])
                expected = state["tradeability"]
                if expected == "TRADE":
                    expected = "WAIT"
                self.assertEqual(self.ranker.call_args.kwargs["tradeability"], expected)

    def test_other_board_vetoes_precede_trade(self):
        for overrides in (
            {"board_tradeability": "WAIT"},
            {"deploy_blocked": True},
            {"should_trade": False},
            {"decision_authority": {"tradeability": "NO_TRADE"}},
            {"decision_authority": {"deploy_blocked": True}},
            {"decision_authority": {"gates": {"regime_wait": True}}},
        ):
            with self.subTest(overrides=overrides):
                self.assert_denied(self.enrich(**overrides))

    def test_preexisting_authority_gates_survive(self):
        from src.services.decision_truth_model import build_decision_authority

        for gate in (
            "engine_off",
            "data_stale",
            "scanner_loading",
            "exec_blocked",
            "broker_offline",
            "fallback_brief",
        ):
            with self.subTest(gate=gate):
                incoming = build_decision_authority(
                    tradeability="TRADE", **{gate: True}
                )
                payload = self.enrich(decision_authority=incoming)
                self.assert_denied(payload)
                self.assertTrue(payload["decision_authority"]["gates"][gate])
                self.assertTrue(incoming["gates"][gate])

    def test_preexisting_authority_ceiling_survives_without_gates(self):
        for ceiling in ("NONE", "RESEARCH", "WATCH"):
            with self.subTest(ceiling=ceiling):
                payload = self.enrich(
                    decision_authority={
                        "gates": {},
                        "allows_trade_labels": False,
                        "authority_level": "research",
                        "effective_action_max": ceiling,
                        "source": "live",
                    }
                )
                self.assert_denied(payload)
                self.assertEqual(
                    payload["decision_authority"]["effective_action_max"],
                    ceiling,
                )

    def test_computed_ceiling_can_be_stricter_than_upstream_watch(self):
        payload = self.enrich(
            stale=True,
            decision_authority={
                "allows_trade_labels": False,
                "authority_level": "research",
                "effective_action_max": "WATCH",
                "source": "live",
            },
        )
        self.assert_denied(payload)
        self.assertEqual(
            payload["decision_authority"]["effective_action_max"], "RESEARCH"
        )

    def test_unknown_upstream_gate_denies_and_survives(self):
        incoming = {
            "allows_trade_labels": True,
            "authority_level": "deploy",
            "effective_action_max": "DEPLOY",
            "source": "live",
            "gates": {"risk_blocked": True},
        }
        original = deepcopy(incoming)
        payload = self.enrich(decision_authority=incoming)
        self.assert_denied(payload)
        self.assertTrue(payload["decision_authority"]["gates"]["risk_blocked"])
        self.assertEqual(incoming, original)

    def test_upstream_source_copy_and_diagnostics_remain_consistent(self):
        from src.services.decision_truth_model import build_decision_authority

        for source in ("stale_cache", "fallback_brief"):
            with self.subTest(source=source):
                incoming = build_decision_authority(
                    tradeability="TRADE", ranked_source=source
                )
                incoming.update(
                    data_source_mismatch=True,
                    data_source_mismatch_detail="SYNTHETIC upstream mismatch",
                    council_count=7,
                )
                original = deepcopy(incoming)
                payload = self.enrich(decision_authority=incoming)
                self.assert_denied(payload)
                authority = payload["decision_authority"]
                self.assertEqual(authority["source"], source)
                self.assertEqual(authority["counter_source"], source)
                self.assertEqual(
                    authority["degraded_copy"]["stale_snapshot_lines"],
                    incoming["degraded_copy"]["stale_snapshot_lines"],
                )
                self.assertEqual(
                    authority["degraded_copy"]["fallback_board_line"],
                    incoming["degraded_copy"]["fallback_board_line"],
                )
                self.assertTrue(authority["data_source_mismatch"])
                self.assertEqual(
                    authority["data_source_mismatch_detail"],
                    incoming["data_source_mismatch_detail"],
                )
                self.assertEqual(authority["council_count"], 7)
                self.assertEqual(incoming, original)

    def test_summary_matches_authorized_rows_on_open_board(self):
        payload = self.enrich()
        summary = payload["best_action"]
        row = payload["opportunities"][0]
        self.assertTrue(payload["decision_authority"]["allows_trade_labels"])
        self.assertEqual(row["effective_action"], "TRADE")
        self.assertEqual(row["pilot_state"], "FULL_DEPLOY")
        self.assertEqual(summary["best_trade_now"]["ticker"], row["ticker"])
        self.assertEqual(summary["execution_ready_count"], 1)
        self.assertEqual(summary["trade_count"], 1)
        self.assertEqual(summary["capital_stance"], "deploy_selectively")
        self.assertTrue(summary["execution_readiness"]["can_send_order"])
        self.assertEqual(payload["decision_authority"]["deploy_ideas_count"], 1)
        self.assertEqual(
            payload["bucket_quality"][0]["deploy_line"], "1/1 execution-ready"
        )

    def test_final_counts_exclude_card_level_downgrade(self):
        payload = self.enrich(
            opportunities=[{**_synthetic_trade(), "risk_reward": None}]
        )
        row = payload["opportunities"][0]
        self.assertEqual(row["effective_action"], "INCOMPLETE")
        self.assertFalse(row["execution_ready"])
        self.assertEqual(payload["decision_authority"]["deploy_ideas_count"], 0)
        self.assertEqual(payload["best_action"]["execution_ready_count"], 0)
        self.assertEqual(
            payload["bucket_quality"][0]["deploy_line"], "0/1 execution-ready"
        )

    def test_grouping_uses_final_authorized_action(self):
        payload = self.enrich(
            opportunities=[{**_synthetic_trade(), "raw_action": "AVOID"}]
        )
        self.assertEqual(payload["opportunities"][0]["action"], "AVOID")
        self.assertEqual(payload["avoid_grouped"]["total"], 1)
        self.assertEqual(payload["decision_authority"]["deploy_ideas_count"], 0)
        self.assertEqual(
            payload["bucket_quality"][0]["deploy_line"], "0/1 execution-ready"
        )

    def test_direct_wait_beats_pilot_logic(self):
        row = {**_synthetic_trade(), "action": "PILOT"}
        summary = build_best_action(
            [row],
            tradeability="WAIT",
            should_trade=True,
            ibkr_connected=True,
        )
        self.assertEqual(summary["capital_stance"], "hold_cash")
        self.assertIsNone(summary["best_pilot_now"])
        self.assertEqual(summary["execution_ready_count"], 0)
        self.assertFalse(summary["execution_readiness"]["can_send_order"])

    def test_canonical_denial_not_overridden_by_connected_bracket(self):
        self.readiness.side_effect = None
        self.readiness.return_value = {"trade_handoff_ready": False}
        summary = build_best_action(
            [_synthetic_trade()],
            tradeability="TRADE",
            ibkr_connected=True,
        )
        self.assertTrue(summary["execution_readiness"]["bracket_ready"])
        self.assertFalse(summary["execution_readiness"]["can_send_order"])

    def test_readiness_exception_denies_connected_bracket(self):
        self.readiness.side_effect = RuntimeError("SYNTHETIC readiness failure")
        summary = build_best_action(
            [_synthetic_trade()],
            tradeability="TRADE",
            ibkr_connected=True,
        )
        self.assertTrue(summary["execution_readiness"]["bracket_ready"])
        self.assertFalse(summary["execution_readiness"]["can_send_order"])
        self.assertFalse(summary["execution_readiness"]["trade_handoff_ready"])

    def test_canonical_broker_state_beats_disagreeing_caller(self):
        self.readiness.side_effect = None
        for canonical_connected in (False, True):
            with self.subTest(canonical_connected=canonical_connected):
                self.readiness.return_value = {
                    "ibkr_connected": canonical_connected,
                    "broker_connected": canonical_connected,
                    "trade_handoff_ready": canonical_connected,
                }
                summary = build_best_action(
                    [_synthetic_trade()],
                    tradeability="TRADE",
                    ibkr_connected=not canonical_connected,
                )
                readiness = summary["execution_readiness"]
                self.assertEqual(readiness["ibkr_connected"], canonical_connected)
                self.assertEqual(readiness["broker_connected"], canonical_connected)
                self.assertEqual(readiness["can_send_order"], canonical_connected)

    def test_canonical_ready_still_requires_open_board(self):
        for overrides in (
            {"tradeability": "WAIT"},
            {"tradeability": "NO_TRADE"},
            {"should_trade": False},
            {"stale": True},
            {"source": "FALLBACK_BRIEF"},
            {"source": "stale_cache"},
        ):
            with self.subTest(overrides=overrides):
                summary = build_best_action(
                    [_synthetic_trade()],
                    **{
                        "tradeability": "TRADE",
                        "ibkr_connected": True,
                        **overrides,
                    }
                )
                self.assertEqual(summary["capital_stance"], "hold_cash")
                self.assertIsNone(summary["best_trade_now"])
                self.assertEqual(summary["execution_ready_count"], 0)
                self.assertFalse(summary["execution_readiness"]["can_send_order"])

    def test_stale_and_fallback_enrichment_deny(self):
        for overrides in (
            {"stale": True},
            {"cached": True},
            {"refreshing": True},
            {"source": "FALLBACK_BRIEF"},
            {"source": "stale_cache"},
            {"board_mode": "compressed_fallback"},
            {"compressed": True},
        ):
            with self.subTest(overrides=overrides):
                self.assert_denied(self.enrich(**overrides))

    def test_construction_and_apply_errors_deny_whole_board(self):
        from src.services.decision_truth_model import (
            apply_authority_to_rows,
            build_decision_authority,
        )

        authority_target = "src.services.decision_truth_model.build_decision_authority"
        apply_target = "src.services.decision_truth_model.apply_authority_to_rows"
        near_miss_target = (
            "src.services.playbook_near_miss.build_playbook_near_miss_rows"
        )
        failures = (
            (authority_target, 0),
            (near_miss_target, 0),
            (apply_target, 1),
            (apply_target, 2),
            (apply_target, 3),
        )
        for target, failure_at in failures:
            for incoming_kind in ("absent", "deploy", "risk_blocked"):
                with self.subTest(
                    target=target,
                    failure_at=failure_at,
                    incoming=incoming_kind,
                ):
                    incoming = build_decision_authority(tradeability="TRADE")
                    if incoming_kind == "risk_blocked":
                        incoming["gates"]["risk_blocked"] = True
                    row = {
                        **_synthetic_trade(),
                        "effective_action": "TRADE",
                        "effective_grade": "TRADE",
                        "pilot_state": "FULL_DEPLOY",
                        "can_send_order": True,
                        "trade_handoff_ready": True,
                        "trade_bar": {
                            "execution_ready": True,
                            "passes_trade_bar": True,
                        },
                        "decision_authority": deepcopy(incoming),
                    }
                    inputs = {
                        "opportunities": [deepcopy(row)],
                        "near_miss": [deepcopy(row)],
                        "near_miss_rows": [deepcopy(row)],
                    }
                    if incoming_kind != "absent":
                        inputs["decision_authority"] = incoming
                    original = deepcopy(inputs)
                    applications = 0

                    def fail_on_surface(rows, authority):
                        nonlocal applications
                        applications += 1
                        if applications == failure_at:
                            # Partial in-place work must never reach the board.
                            rows[0]["action"] = "PILOT"
                            rows[0]["trade_bar"]["execution_ready"] = False
                            raise RuntimeError("SYNTHETIC apply failure")
                        return apply_authority_to_rows(rows, authority)

                    effect = (
                        fail_on_surface
                        if target == apply_target
                        else RuntimeError("SYNTHETIC construction failure")
                    )
                    with patch(near_miss_target, return_value=[deepcopy(row)]), patch(
                        target, side_effect=effect
                    ):
                        payload = self.enrich(**inputs)
                    self.assert_denied(payload)
                    authority = payload["decision_authority"]
                    self.assertEqual(authority["authority_level"], "suspended")
                    self.assertEqual(authority["effective_action_max"], "NONE")
                    self.assertTrue(authority["gates"]["exec_blocked"])
                    if incoming_kind == "risk_blocked":
                        self.assertTrue(authority["gates"]["risk_blocked"])
                    for key in ("opportunities", "near_miss", "near_miss_rows"):
                        self.assertEqual(len(payload[key]), 1)
                        denied = payload[key][0]
                        self.assertEqual(denied["effective_action"], "NONE")
                        self.assertEqual(denied["effective_grade"], "NONE")
                        self.assertEqual(denied["pilot_state"], "BLOCKED")
                        self.assertFalse(denied["can_send_order"])
                        self.assertFalse(denied["trade_handoff_ready"])
                        self.assertFalse(denied["trade_bar"]["execution_ready"])
                        self.assertFalse(denied["trade_bar"]["passes_trade_bar"])
                    self.assertEqual(inputs, original)


if __name__ == "__main__":
    unittest.main()
