"""Actual Today handler regressions; all market inputs are SYNTHETIC.

Load AST nodes from decision.py, never import the router or API startup.
TRADE fixtures use R:R 3:1; canonical readiness is mocked ready so board
vetoes must independently prevent handoff.
"""

import ast
import asyncio
import logging
import sys
import time
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.services.best_action import build_best_action
from src.services.decision_truth_model import build_decision_authority

ROUTER = Path(__file__).resolve().parents[1] / "src/api/routers/decision.py"


def _handler(name):
    tree = ast.parse(ROUTER.read_text(encoding="utf-8"), filename=str(ROUTER))
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    ]
    assert len(matches) == 1, f"Expected actual {name} in {ROUTER}"
    return matches[0]


def _assigns(node, name):
    return isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == name for target in node.targets
    )


def _load_handler(node, namespace, initialize=()):
    node = deepcopy(node)
    node.decorator_list = []
    node.returns = None
    node.args.defaults = []
    for argument in node.args.args:
        argument.annotation = None
    # Inject fixture values for locals initialized in the skipped scan portion.
    setup = []
    for name in initialize:
        fixture_name = f"_fixture_{name}"
        namespace[fixture_name] = namespace[name]
        setup.append(
            ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.Name(id=fixture_name, ctx=ast.Load()),
            )
        )
    node.body = setup + node.body
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(ROUTER), "exec"), namespace)  # noqa: S102
    return namespace[node.name]


def _synthetic_trade(ticker="SYNTH"):
    return {
        "ticker": ticker,
        "action": "TRADE",
        "execution_ready": True,
        "entry_price": 100.0,
        "stop_price": 90.0,
        "target_price": 130.0,
        "risk_reward": 3.0,
        "score": 8.5,
        "final_conf": 0.75,
        "thesis_conf": 0.75,
        "timing_conf": 0.75,
        "exec_conf": 0.75,
        "data_conf": 0.75,
        "evidence_badge": "SYNTHETIC",
    }


def _module(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


class TestTodayBestActionAuthority(unittest.TestCase):
    def setUp(self):
        self.request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        self.ops = {"running": True, "breaker": False}
        self.broker = {"connected": True, "session_usable": True, "mode": "paper"}
        self.regime = SimpleNamespace(should_trade=True, regime="RISK_ON")
        self.readiness = Mock(
            side_effect=lambda **kwargs: {
                "trade_handoff_ready": True,
                "ibkr_connected": self.broker["connected"],
                "broker_connected": self.broker["connected"],
                "engine_running": self.ops["running"],
                "circuit_breaker": self.ops["breaker"],
                "mode": "paper",
            }
        )
        # No real broker, engine, market-data, or API module is imported.
        modules = {
            "src.api.app_state": _module(
                "src.api.app_state", get_engine=Mock(return_value=object())
            ),
            "src.services.ibkr_service": _module(
                "src.services.ibkr_service",
                get_ibkr_service=lambda: SimpleNamespace(status=lambda: self.broker),
            ),
            "src.services.execution_readiness": _module(
                "src.services.execution_readiness",
                build_execution_readiness=self.readiness,
            ),
            "src.services.runtime_truth": _module(
                "src.services.runtime_truth",
                engine_runtime_snapshot=lambda engine: {
                    "running": self.ops["running"],
                    "circuit_breaker": self.ops["breaker"],
                },
                merge_execution_runtime_truth=lambda readiness, **kwargs: readiness,
            ),
            "src.services.cc_state": _module(
                "src.services.cc_state",
                build_cc_state=lambda **kwargs: {
                    "tradeability_state": {
                        "tradeability": kwargs["tradeability"],
                        "should_trade": kwargs["should_trade"],
                    }
                },
                attach_system_state=lambda payload: payload,
                attach_page_capability=lambda payload, page: payload,
            ),
            "src.services.decision_board_service": _module(
                "src.services.decision_board_service",
                attach_decision_board=Mock(
                    side_effect=lambda payload, **kwargs: payload
                ),
            ),
        }
        self.enterContext(patch.dict(sys.modules, modules))
        self.namespace = {
            "logger": logging.getLogger(__name__),
            "_fetch_regime": AsyncMock(side_effect=lambda request: self.regime),
            "_board_ops_snapshot": lambda request: dict(self.ops),
            "sanitize_for_json": lambda payload: payload,
        }

    def fresh(
        self,
        *,
        final="TRADE",
        should_trade=True,
        stale=False,
        fallback=False,
        rows=None,
        pipeline_rows=None,
    ):
        node = _handler("today_summary")
        start = next(
            i
            for i, part in enumerate(node.body)
            if _assigns(part, "all_opps_for_action")
        )
        end = next(
            i
            for i, part in enumerate(node.body)
            if _assigns(part, "cross_asset_confirmation")
        )
        pipe_start = next(
            i for i, part in enumerate(node.body) if _assigns(part, "_pipe")
        )
        pipe_end = next(
            i for i, part in enumerate(node.body) if _assigns(part, "todays_decision")
        )
        payload_node = deepcopy(
            next(part for part in node.body if _assigns(part, "payload"))
        )
        # Retain actual cache fields, without unrelated surfaces.
        payload_keys = {
            "market_regime",
            "top_5",
            "top_ranked",
            "opportunities",
            "best_action",
            "decision_authority",
            "decision_model",
            "trust",
            "filter_funnel",
            "generated_at",
        }
        fields = [
            (key, value)
            for key, value in zip(payload_node.value.keys, payload_node.value.values)
            if isinstance(key, ast.Constant) and key.value in payload_keys
        ]
        payload_node.value.keys = [key for key, _ in fields]
        payload_node.value.values = [value for _, value in fields]
        cache_node = deepcopy(
            next(
                part
                for part in node.body
                if isinstance(part, ast.If)
                and any(_assigns(child, "_today_cache") for child in part.body)
            )
        )
        # Execute two actual contiguous handler portions; skip market/AI calls.
        node.body = (
            [node.body[0]]  # Actual global cache declaration.
            + node.body[start:end]
            + node.body[pipe_start:pipe_end]
            + [payload_node, cache_node]
        )
        node.body.append(
            ast.Return(
                value=ast.Dict(
                    keys=[
                        ast.Constant(key)
                        for key in (
                            "best_action",
                            "rows",
                            "authority",
                            "payload",
                            "cache",
                        )
                    ],
                    values=[
                        ast.Name(id=name, ctx=ast.Load())
                        for name in (
                            "best_action",
                            "all_opps_for_action",
                            "decision_authority",
                            "payload",
                            "_today_cache",
                        )
                    ],
                )
            )
        )
        rows = deepcopy(rows if rows is not None else [_synthetic_trade()])
        namespace = {
            **self.namespace,
            "_row_for_action": lambda row: dict(row),
            "sorted_council": rows,
            "council_results": rows,
            "scanned": rows,
            "top5": deepcopy(rows[:5]),
            "near_miss": [],
            "tradeability": "WAIT" if should_trade else "NO_TRADE",
            "should_trade": should_trade,
            "regime_label": "RISK_ON",
            "trend_label": "UPTREND",
            "vix_val": 18.0,
            "breadth_val": 60.0,
            "execution_ready_count": len(rows),
            "pilot_ready_count": 0,
            "scanner_degraded": stale,
            "used_brief_fallback": fallback,
            "now": datetime(2026, 10, 13, tzinfo=timezone.utc),
            "build_three_layer_model": Mock(
                return_value={"honest_tradeability": final}
            ),
            "funnel": {"execution_ready_setups": len(rows)},
            "time": time,
            "risk_state": "RISK_ON",
            "confidence": 0.75,
            "narrative": "SYNTHETIC fixture",
            "vol_label": "NORMAL",
            "score": 75,
            "breadth": 0.6,
            "entropy": 1.0,
            "trust": {"source": "decision_engine", "stale": stale or fallback},
            "brief_ctx": {},
            "_quality_stale": stale or fallback,
            "_brief_stale": False,
            "index_regime_summary": {},
            "finalize_opportunity_pipeline": Mock(
                side_effect=lambda payload, **kwargs: {
                    **payload,
                    **(
                        {"opportunities": pipeline_rows}
                        if pipeline_rows is not None
                        else {}
                    ),
                }
            ),
        }
        function = _load_handler(
            node, namespace, initialize=("tradeability", "top5", "near_miss")
        )
        return asyncio.run(function(self.request, True))

    def cached(self, payload):
        function = _load_handler(_handler("_refresh_today_authority"), self.namespace)
        original = deepcopy(payload)
        result = asyncio.run(function(self.request, payload))
        self.assertEqual(
            payload, original, "Refreshing must not mutate the cached snapshot"
        )
        return result

    def payload(self):
        row = _synthetic_trade()
        return {
            "market_regime": {
                "tradeability": "TRADE",
                "should_trade": True,
                "label": "RISK_ON",
            },
            "decision_model": {"honest_tradeability": "TRADE"},
            "decision_authority": build_decision_authority(tradeability="TRADE"),
            "top_ranked": [row],
            "top_5": [deepcopy(row)],
            "near_miss": [deepcopy(row)],
            "trust": {"source": "decision_engine", "stale": False},
            "filter_funnel": {"execution_ready_setups": 1},
            "generated_at": "2026-10-13T00:00:00Z",
            "best_action": build_best_action(
                [row], tradeability="TRADE", ibkr_connected=True
            ),
        }

    def assert_denied(self, summary):
        self.assertEqual(summary["capital_stance"], "hold_cash")
        self.assertIsNone(summary["best_trade_now"])
        self.assertIsNone(summary["best_pilot_now"])
        self.assertEqual(summary["execution_ready_count"], 0)
        self.assertFalse(summary["execution_readiness"]["can_send_order"])
        self.assertTrue(summary["execution_readiness"]["trade_handoff_ready"])

    def test_actual_handler_builds_summary_once_after_final_rows(self):
        node = _handler("today_summary")
        calls = [
            part
            for part in ast.walk(node)
            if isinstance(part, ast.Call)
            and isinstance(part.func, ast.Name)
            and part.func.id == "build_best_action"
        ]
        self.assertEqual(len(calls), 1)
        final_rows = next(
            part for part in node.body if _assigns(part, "_opportunity_verdict")
        )
        self.assertGreater(calls[0].lineno, final_rows.lineno)

    def test_fresh_open_board_uses_final_tradeability_and_authorized_rows(self):
        result = self.fresh()
        summary = result["best_action"]
        self.assertTrue(result["authority"]["allows_trade_labels"])
        self.assertEqual(result["rows"][0]["effective_action"], "TRADE")
        self.assertEqual(summary["tradeability"], "TRADE")
        self.assertEqual(summary["best_trade_now"]["ticker"], "SYNTH")
        self.assertEqual(summary["execution_ready_count"], 1)
        self.assertEqual(summary["capital_stance"], "deploy_selectively")
        self.assertTrue(summary["execution_readiness"]["can_send_order"])

    def test_fresh_wait_and_should_trade_veto_cannot_be_upgraded(self):
        for inputs in (
            {"final": "WAIT"},
            {"final": "NO_TRADE"},
            {"should_trade": False},
        ):
            with self.subTest(inputs=inputs):
                self.assert_denied(self.fresh(**inputs)["best_action"])

    def test_fresh_runtime_and_data_vetoes_survive_ready_handoff(self):
        for gate in ("breaker", "engine_off", "broker_offline", "stale", "fallback"):
            with self.subTest(gate=gate):
                self.ops.update(running=gate != "engine_off", breaker=gate == "breaker")
                self.broker["connected"] = gate != "broker_offline"
                result = self.fresh(stale=gate == "stale", fallback=gate == "fallback")
                self.assertFalse(result["authority"]["allows_trade_labels"])
                self.assert_denied(result["best_action"])

    def test_fresh_summary_excludes_authority_and_pipeline_downgrades(self):
        for inputs in (
            {"rows": [{**_synthetic_trade(), "risk_reward": None}]},
            {"pipeline_rows": []},
            {
                "pipeline_rows": [
                    {
                        **_synthetic_trade(),
                        "action": "WATCH",
                        "effective_action": "WATCH",
                        "execution_ready": False,
                    }
                ]
            },
        ):
            with self.subTest(inputs=inputs):
                self.assert_denied(self.fresh(**inputs)["best_action"])

    def test_cached_open_board_rebuilds_summary(self):
        payload = self.payload()
        payload["best_action"] = {"capital_stance": "hold_cash"}
        result = self.cached(payload)
        self.assertEqual(result["best_action"]["capital_stance"], "deploy_selectively")
        self.assertEqual(result["best_action"]["best_trade_now"]["ticker"], "SYNTH")
        self.assertTrue(result["best_action"]["execution_readiness"]["can_send_order"])

    def test_fresh_to_cache_preserves_full_candidates_and_counts(self):
        rows = [_synthetic_trade(f"SYNTH{i}") for i in range(7)]
        original = deepcopy(rows)
        fresh = self.fresh(rows=rows)
        self.assertEqual(rows, original)
        self.assertEqual(len(fresh["payload"]["top_ranked"]), 5)
        self.assertEqual(fresh["payload"]["opportunities"], fresh["rows"])
        self.assertEqual(fresh["cache"], fresh["payload"])
        cached = self.cached(fresh["cache"])
        self.assertEqual(len(cached["opportunities"]), 7)
        self.assertEqual(fresh["best_action"]["execution_ready_count"], 7)
        self.assertEqual(cached["best_action"], fresh["best_action"])

    def test_fresh_to_cache_keeps_valid_sixth_after_incomplete_first_five(self):
        rows = [
            {**_synthetic_trade(f"SYNTH{i}"), "risk_reward": None} for i in range(5)
        ] + [_synthetic_trade("SYNTH6")]
        original = deepcopy(rows)
        fresh = self.fresh(rows=rows)
        self.assertEqual(rows, original)
        self.assertEqual(fresh["best_action"]["best_trade_now"]["ticker"], "SYNTH6")
        self.assertEqual(fresh["best_action"]["execution_ready_count"], 1)
        cached = self.cached(fresh["cache"])
        self.assertEqual(len(cached["opportunities"]), 6)
        self.assertEqual(cached["best_action"], fresh["best_action"])
        self.assertEqual(cached["opportunities"][5]["effective_action"], "TRADE")
        self.ops["breaker"] = True
        blocked = self.cached(fresh["cache"])
        self.assert_denied(blocked["best_action"])
        self.assertEqual(len(blocked["opportunities"]), 6)
        for row in blocked["opportunities"]:
            self.assertNotEqual(row["effective_action"], "TRADE")

    def test_fresh_to_cache_preserves_explicit_empty_final_opportunities(self):
        fresh = self.fresh(pipeline_rows=[])
        self.assertTrue(fresh["payload"]["top_ranked"])
        self.assertEqual(fresh["payload"]["opportunities"], [])
        self.assert_denied(fresh["best_action"])
        cached = self.cached(fresh["cache"])
        self.assertEqual(cached["opportunities"], [])
        self.assert_denied(cached["best_action"])

    def test_cached_explicit_empty_does_not_fall_back_to_ranked_rows(self):
        payload = self.payload()
        payload["opportunities"] = []
        result = self.cached(payload)
        self.assertEqual(result["opportunities"], [])
        self.assert_denied(result["best_action"])

    def test_cached_legacy_payload_falls_back_to_each_ranked_key(self):
        for key in ("top_ranked", "top_5"):
            with self.subTest(key=key):
                payload = self.payload()
                self.assertNotIn("opportunities", payload)
                payload.pop("top_5" if key == "top_ranked" else "top_ranked")
                result = self.cached(payload)
                self.assertEqual(
                    result["best_action"]["best_trade_now"]["ticker"], "SYNTH"
                )
                self.assertEqual(result["best_action"]["execution_ready_count"], 1)

    def test_cached_board_wait_and_should_trade_veto_beat_optimistic_model(self):
        for location, veto in (
            ("market_regime", {"tradeability": "WAIT"}),
            ("market_regime", {"tradeability": "NO_TRADE"}),
            ("market_regime", {"should_trade": False}),
            ("board", {"tradeability": "WAIT"}),
            ("board", {"should_trade": False}),
            ("board", {"deploy_blocked": True}),
            ("decision_board", {"deploy_open": False}),
            ("system_state", {"deploy_open": False}),
        ):
            with self.subTest(location=location, veto=veto):
                payload = self.payload()
                if location == "board":
                    payload["cc_state"] = {"tradeability_state": veto}
                elif location in ("decision_board", "system_state"):
                    payload[location] = veto
                else:
                    payload[location].update(veto)
                self.assert_denied(self.cached(payload)["best_action"])

    def test_cached_live_vetoes_replace_old_trade_summary_and_reauthorize_rows(self):
        for gate in ("breaker", "engine_off", "broker_offline", "regime"):
            with self.subTest(gate=gate):
                payload = self.payload()
                self.ops.update(running=gate != "engine_off", breaker=gate == "breaker")
                self.broker.update(
                    connected=gate != "broker_offline",
                    session_usable=gate != "broker_offline",
                )
                self.regime.should_trade = gate != "regime"
                result = self.cached(payload)
                self.assert_denied(result["best_action"])
                for key in ("top_5", "top_ranked", "near_miss"):
                    self.assertNotEqual(result[key][0]["effective_action"], "TRADE")

    def test_cached_prior_gates_and_ceilings_never_reopen(self):
        vetoes = [
            {"gates": {gate: True}}
            for gate in (
                "regime_wait",
                "engine_off",
                "data_stale",
                "broker_offline",
                "scanner_loading",
                "exec_blocked",
                "fallback_brief",
                "risk_blocked",
            )
        ] + [
            {"allows_trade_labels": False, "effective_action_max": ceiling}
            for ceiling in ("NONE", "RESEARCH", "WATCH")
        ]
        for veto in vetoes:
            with self.subTest(veto=veto):
                payload = self.payload()
                payload["decision_authority"].update(veto)
                result = self.cached(payload)
                self.assert_denied(result["best_action"])
                self.assertFalse(result["decision_authority"]["allows_trade_labels"])
                for gate in veto.get("gates", {}):
                    self.assertTrue(result["decision_authority"]["gates"][gate])
                if veto.get("effective_action_max") == "NONE":
                    self.assertEqual(
                        result["decision_authority"]["effective_action_max"], "NONE"
                    )

    def test_cached_stale_and_fallback_sources_deny(self):
        for trust in (
            {"source": "decision_engine", "stale": True},
            {"source": "brief-fallback", "stale": False},
        ):
            with self.subTest(trust=trust):
                payload = self.payload()
                payload["trust"] = trust
                self.assert_denied(self.cached(payload)["best_action"])


if __name__ == "__main__":
    unittest.main()
