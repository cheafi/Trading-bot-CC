"""
Decision Persistence — Learning Loop Storage.

Persists to JSON files:
1. Decision Journal — every signal + outcome
2. Expert Track Record — per-expert accuracy
3. Calibration Data — Brier scores by confidence bucket

This closes the open loop:
generate signal → track outcome → learn from results.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "artifacts")


# ── Decision Journal ──────────────────────────────────


class DecisionJournal:
    """
    Persist every trading decision for outcome tracking.

    Each entry:
    - signal metadata (ticker, date, confidence, tier)
    - predicted probability
    - actual outcome (filled later)
    - Brier score (computed on resolution)
    """

    def __init__(
        self,
        path: Optional[str] = None,
    ):
        self.path = (
            path
            or os.getenv("DECISION_JOURNAL_PATH")
            or os.path.join(_DATA_DIR, "decision_journal.jsonl")
        )
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def record(
        self,
        ticker: str,
        decision_tier: str,
        composite_score: float,
        should_trade: bool,
        regime: str = "unknown",
        sector: str = "unknown",
        entry_price: float = 0.0,
        stop_price: float = 0.0,
        target_price: float = 0.0,
        expert_consensus: str = "unknown",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a new decision."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker,
            "decision_tier": decision_tier,
            "composite_score": round(composite_score, 1),
            "predicted_prob": round(composite_score / 100, 3),
            "should_trade": should_trade,
            "regime": regime,
            "sector": sector,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "expert_consensus": expert_consensus,
            "outcome": None,
            "outcome_date": None,
            "brier_score": None,
        }
        if extra:
            entry.update(extra)

        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Failed to write decision journal: %s", e)

        return entry

    def record_recommendation(
        self,
        recommendation: Dict[str, Any],
        *,
        source: str,
        mode: str,
        regime: str = "unknown",
        response_trust: Optional[Dict[str, Any]] = None,
        data_freshness: Optional[Dict[str, Any]] = None,
        dedupe_window_seconds: int = 300,
        recent_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Record one canonical recommendation snapshot.

        Keeps the learning loop append-only while avoiding duplicate rows from
        repeated dashboard refreshes over the same recommendation snapshot.
        """
        if not isinstance(recommendation, dict) and hasattr(recommendation, "__dict__"):
            recommendation = dict(recommendation.__dict__)
        if not isinstance(recommendation, dict):
            return {}

        ticker = (
            str(recommendation.get("ticker") or recommendation.get("symbol") or "")
            .upper()
            .strip()
        )
        if not ticker:
            return {}

        action_state = recommendation.get("action_state") or {}
        if not isinstance(action_state, dict):
            action_state = {}
        calibrated = recommendation.get("calibrated_confidence") or {}
        if not isinstance(calibrated, dict):
            calibrated = {}
        trust_strip = recommendation.get("trust_strip") or {}
        if not isinstance(trust_strip, dict):
            trust_strip = {}

        confidence = self._as_float(
            recommendation.get("confidence"),
            self._as_float(recommendation.get("score"), 0.0) * 10,
        )
        if 0 < confidence <= 1:
            confidence *= 100
        confidence = max(0.0, min(100.0, confidence))

        entry_price = self._as_float(recommendation.get("entry_price"), 0.0)
        stop_price = self._as_float(
            recommendation.get("stop_price") or recommendation.get("stop_loss"), 0.0
        )
        target_price = self._as_float(
            recommendation.get("target_price") or recommendation.get("take_profit"),
            0.0,
        )
        rr = self._as_float(
            recommendation.get("risk_reward") or recommendation.get("rr"), 0.0
        )
        if rr <= 0 and entry_price and stop_price and target_price:
            risk = abs(entry_price - stop_price)
            reward = abs(target_price - entry_price)
            rr = round(reward / risk, 2) if risk > 0 else 0.0

        decision_tier = str(
            action_state.get("action")
            or recommendation.get("action")
            or recommendation.get("decision_tier")
            or recommendation.get("grade")
            or "WATCH"
        )
        strategy = str(recommendation.get("strategy") or "unknown")

        if self._is_duplicate_recommendation(
            ticker=ticker,
            source=source,
            mode=mode,
            strategy=strategy,
            decision_tier=decision_tier,
            entry_price=entry_price,
            window=timedelta(seconds=dedupe_window_seconds),
            recent_entries=recent_entries,
        ):
            return {
                "record_type": "recommendation",
                "ticker": ticker,
                "deduped": True,
            }

        confidence_source = (
            "calibrated_confidence"
            if calibrated.get("forecast_probability") is not None
            else "raw_recommendation_confidence"
        )
        response_trust = response_trust or {}
        merged_trust = {
            **response_trust,
            **trust_strip,
            "recommendation_source": source,
            "confidence_source": confidence_source,
        }

        return self.record(
            ticker=ticker,
            decision_tier=decision_tier,
            composite_score=confidence,
            should_trade=decision_tier.upper() in {"TRADE", "BUY", "STRONG_BUY"},
            regime=str(recommendation.get("regime") or regime or "unknown"),
            sector=str(recommendation.get("sector") or "unknown"),
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            expert_consensus=str(recommendation.get("expert_consensus") or "system"),
            extra={
                "record_type": "recommendation",
                "ledger_version": 1,
                "mode": mode,
                "recommendation_source": source,
                "strategy": strategy,
                "direction": recommendation.get("direction", "LONG"),
                "score": self._as_float(recommendation.get("score"), 0.0),
                "risk_reward": rr,
                "grade": recommendation.get("grade"),
                "confidence": round(confidence, 2),
                "confidence_source": confidence_source,
                "forecast_probability": calibrated.get(
                    "forecast_probability", round(confidence / 100, 3)
                ),
                "historical_reliability_bucket": calibrated.get(
                    "historical_reliability_bucket"
                ),
                "uncertainty_band": calibrated.get("uncertainty_band"),
                "data_freshness": data_freshness,
                "trust_strip": merged_trust,
            },
        )

    def record_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        *,
        source: str,
        mode: str,
        regime: str = "unknown",
        response_trust: Optional[Dict[str, Any]] = None,
        data_freshness: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a batch of recommendation snapshots."""
        written = 0
        deduped = 0
        recent_entries = self._load_all()[-200:]
        for recommendation in recommendations:
            if not isinstance(recommendation, dict) and hasattr(
                recommendation, "__dict__"
            ):
                recommendation = dict(recommendation.__dict__)
            if not isinstance(recommendation, dict):
                continue
            entry = self.record_recommendation(
                recommendation,
                source=source,
                mode=mode,
                regime=regime,
                response_trust=response_trust,
                data_freshness=data_freshness,
                recent_entries=recent_entries,
            )
            if entry.get("deduped"):
                deduped += 1
            elif entry:
                written += 1
                recent_entries.append(entry)
                recent_entries = recent_entries[-200:]
        return {"written": written, "deduped": deduped}

    def get_recent_recommendations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent recommendation ledger entries only."""
        entries = [
            entry
            for entry in self._load_all()
            if entry.get("record_type") == "recommendation"
        ]
        return entries[-limit:]

    def resolve(
        self,
        ticker: str,
        outcome: str,
        actual_return_pct: float = 0.0,
    ):
        """
        Resolve a pending decision with actual outcome.

        outcome: "win", "loss", "scratch", "stopped_out"
        """
        entries = self._load_all()
        updated = False

        for entry in reversed(entries):
            if entry.get("ticker") == ticker and entry.get("outcome") is None:
                entry["outcome"] = outcome
                entry["outcome_date"] = datetime.now(timezone.utc).isoformat()
                entry["actual_return_pct"] = actual_return_pct
                # Brier score: (predicted - actual)^2
                actual = 1.0 if outcome == "win" else 0.0
                pred = entry.get("predicted_prob", 0.5)
                entry["brier_score"] = round((pred - actual) ** 2, 4)
                updated = True
                break

        if updated:
            self._save_all(entries)

    def get_recent(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent decisions."""
        entries = self._load_all()
        return entries[-limit:]

    def get_calibration(self) -> Dict[str, Any]:
        """
        Calibration report: Brier scores by bucket.

        Low Brier = well-calibrated.
        """
        entries = self._load_all()
        resolved = [e for e in entries if e.get("brier_score") is not None]
        if not resolved:
            return {
                "total_resolved": 0,
                "avg_brier": None,
                "buckets": {},
            }

        buckets = {
            "high": [],
            "medium": [],
            "low": [],
        }
        for e in resolved:
            bucket = e.get("confidence_bucket", "medium")
            if e["composite_score"] >= 70:
                bucket = "high"
            elif e["composite_score"] >= 50:
                bucket = "medium"
            else:
                bucket = "low"
            buckets[bucket].append(e["brier_score"])

        return {
            "total_resolved": len(resolved),
            "avg_brier": round(
                sum(e["brier_score"] for e in resolved) / len(resolved), 4
            ),
            "buckets": {
                k: {
                    "count": len(v),
                    "avg_brier": (round(sum(v) / len(v), 4) if v else None),
                }
                for k, v in buckets.items()
            },
            "win_rate": round(
                sum(1 for e in resolved if e.get("outcome") == "win")
                / len(resolved)
                * 100,
                1,
            ),
        }

    def _load_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        entries = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _is_duplicate_recommendation(
        self,
        *,
        ticker: str,
        source: str,
        mode: str,
        strategy: str,
        decision_tier: str,
        entry_price: float,
        window: timedelta,
        recent_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        cutoff = datetime.now(timezone.utc) - window
        entries = (
            recent_entries if recent_entries is not None else self._load_all()[-200:]
        )
        for entry in reversed(entries):
            if entry.get("record_type") != "recommendation":
                continue
            try:
                ts = datetime.fromisoformat(str(entry.get("timestamp", "")))
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                return False
            if (
                entry.get("ticker") == ticker
                and entry.get("recommendation_source") == source
                and entry.get("mode") == mode
                and entry.get("strategy") == strategy
                and entry.get("decision_tier") == decision_tier
                and abs(self._as_float(entry.get("entry_price"), 0.0) - entry_price)
                < 0.01
            ):
                return True
        return False

    def _save_all(
        self,
        entries: List[Dict[str, Any]],
    ):
        with open(self.path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")


# ── Expert Track Record Persistence ───────────────────


class ExpertRecordStore:
    """
    Persist expert accuracy across restarts.

    Tracks per-expert: total predictions, correct,
    accuracy rate, and reliability weight.
    """

    def __init__(
        self,
        path: Optional[str] = None,
    ):
        self.path = (
            path
            or os.getenv("EXPERT_TRACK_RECORD_PATH")
            or os.path.join(_DATA_DIR, "expert_track_record.json")
        )
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.records: Dict[str, Dict[str, Any]] = {}
        self._load()

    def update(
        self,
        role: str,
        predicted_stance: str,
        was_correct: bool,
    ):
        """Record an expert prediction outcome."""
        if role not in self.records:
            self.records[role] = {
                "total": 0,
                "correct": 0,
                "accuracy": 0.5,
            }
        rec = self.records[role]
        rec["total"] += 1
        rec["correct"] += int(was_correct)
        rec["accuracy"] = round(rec["correct"] / rec["total"], 4)
        self._save()

    def get_weight(self, role: str) -> float:
        """
        Reliability weight for expert (0.5 — 1.5).

        No track record = 1.0 (equal weight).
        """
        rec = self.records.get(role)
        if rec is None or rec["total"] < 10:
            return 1.0
        acc = max(0.3, min(0.7, rec["accuracy"]))
        return 0.5 + (acc - 0.3) / 0.4 * 1.0

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all expert records with weights."""
        result = {}
        for role, rec in self.records.items():
            result[role] = {
                **rec,
                "weight": round(self.get_weight(role), 2),
            }
        return result

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path) as f:
                self.records = json.load(f)
            logger.info(
                "Loaded expert records for %d roles",
                len(self.records),
            )
        except Exception as e:
            logger.warning("Failed to load expert records: %s", e)

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.records, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save expert records: %s", e)


# ── Singletons ────────────────────────────────────────

_journal = DecisionJournal()
_expert_store = ExpertRecordStore()


def get_journal() -> DecisionJournal:
    return _journal


def get_expert_store() -> ExpertRecordStore:
    return _expert_store
