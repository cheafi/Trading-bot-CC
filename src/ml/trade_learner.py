"""
TradingAI Bot - ML Trade Learner

Learns from every trade (wins AND losses) to continuously improve:
1. Records full context of every trade outcome
2. Trains gradient-boosted models on trade features → outcome
3. Uses LLM to analyze failure patterns in natural language
4. Adjusts strategy parameters based on learned patterns
5. Produces actionable insights for the AI advisor

Architecture:
  Trade Outcomes DB → Feature Extraction → Model Training → Prediction
                    → LLM Failure Analysis → Strategy Tuning

Model serialization: uses joblib with versioned filenames to avoid
pickle security issues and sklearn version incompatibilities.
"""
import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.config import get_settings, get_trading_config

logger = logging.getLogger(__name__)
settings = get_settings()
trading_config = get_trading_config()

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)

# Model version — bump when changing feature set or model architecture
_MODEL_VERSION = "v2"


# ---------------------------------------------------------------------------
# Trade outcome record
# ---------------------------------------------------------------------------

class TradeOutcomeRecord:
    """Complete record of a trade for learning."""

    def __init__(
        self,
        trade_id: str,
        ticker: str,
        direction: str,
        strategy: str,
        entry_price: float,
        exit_price: float,
        entry_time: str,
        exit_time: str,
        pnl_pct: float,
        confidence: int,
        horizon: str,
        # Context at entry
        market_regime: str = "",
        vix_at_entry: float = 0.0,
        rsi_at_entry: float = 0.0,
        adx_at_entry: float = 0.0,
        relative_volume: float = 0.0,
        distance_from_sma50: float = 0.0,
        sector: str = "",
        # Outcome details
        max_favorable_excursion: float = 0.0,
        max_adverse_excursion: float = 0.0,
        exit_reason: str = "",  # target_hit, stop_hit, time_exit, manual
        hold_hours: float = 0.0,
        # Feature snapshot
        feature_snapshot: Optional[Dict[str, Any]] = None,
    ):
        self.data = {
            "trade_id": trade_id,
            "ticker": ticker,
            "direction": direction,
            "strategy": strategy,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "pnl_pct": pnl_pct,
            "is_winner": pnl_pct > 0,
            "confidence": confidence,
            "horizon": horizon,
            "market_regime": market_regime,
            "vix_at_entry": vix_at_entry,
            "rsi_at_entry": rsi_at_entry,
            "adx_at_entry": adx_at_entry,
            "relative_volume": relative_volume,
            "distance_from_sma50": distance_from_sma50,
            "sector": sector,
            "max_favorable_excursion": max_favorable_excursion,
            "max_adverse_excursion": max_adverse_excursion,
            "exit_reason": exit_reason,
            "hold_hours": hold_hours,
        }
        if feature_snapshot:
            self.data.update(
                {f"feat_{k}": v for k, v in feature_snapshot.items()
                 if isinstance(v, (int, float))}
            )

    def to_dict(self) -> Dict[str, Any]:
        return self.data


# ---------------------------------------------------------------------------
# ML Trade Outcome Predictor
# ---------------------------------------------------------------------------

class TradeOutcomePredictor:
    """
    Gradient-boosted model that predicts trade success probability.
    
    Features → P(win), Expected P&L, Optimal position size
    
    Trains on historical trade outcomes and continuously improves
    as more data accumulates.
    """

    FEATURE_COLS = [
        "confidence", "vix_at_entry", "rsi_at_entry", "adx_at_entry",
        "relative_volume", "distance_from_sma50",
    ]

    def __init__(self):
        self.model = None
        self.scaler = None
        self._model_path = MODEL_DIR / f"trade_outcome_model_{_MODEL_VERSION}.joblib"
        self._legacy_path = MODEL_DIR / "trade_outcome_model.pkl"
        self._history: List[Dict[str, Any]] = []
        self._min_samples = 30  # minimum trades before training
        self._load_model()

    def _load_model(self):
        """Load model from versioned joblib file, with pickle fallback."""
        # Try joblib first (preferred)
        if self._model_path.exists():
            try:
                import joblib
                saved = joblib.load(self._model_path)
                self.model = saved.get("model")
                self.scaler = saved.get("scaler")
                version = saved.get("version", "unknown")
                logger.info("Loaded trade outcome model (version=%s)", version)
                return
            except ImportError:
                logger.warning("joblib not installed — falling back to pickle")
            except Exception as e:
                logger.warning("Could not load joblib model: %s", e)

        # Fallback: legacy pickle file (one-time migration)
        if self._legacy_path.exists():
            try:
                import pickle
                with open(self._legacy_path, "rb") as f:
                    saved = pickle.load(f)
                self.model = saved.get("model")
                self.scaler = saved.get("scaler")
                logger.info("Loaded legacy pickle model — will re-save as joblib")
                self._save_model()  # migrate to joblib
                return
            except Exception as e:
                logger.warning("Could not load legacy model: %s", e)

    def _save_model(self):
        """Save model using joblib with version metadata."""
        try:
            import joblib
            payload = {
                "model": self.model,
                "scaler": self.scaler,
                "version": _MODEL_VERSION,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "feature_cols": self.FEATURE_COLS,
            }
            joblib.dump(payload, self._model_path)
            logger.info("Saved trade outcome model (version=%s)", _MODEL_VERSION)
        except ImportError:
            logger.error("joblib not installed: pip install joblib")
        except Exception as e:
            logger.error("Could not save model: %s", e)

    def add_outcome(self, record: TradeOutcomeRecord):
        """Add a trade outcome for learning."""
        self._history.append(record.to_dict())
        logger.info(
            f"Recorded trade outcome: {record.data['ticker']} "
            f"{'WIN' if record.data['is_winner'] else 'LOSS'} "
            f"{record.data['pnl_pct']:+.2f}%"
        )

    def train(self) -> Dict[str, Any]:
        """
        Train the model on accumulated trade outcomes.
        Returns training metrics.
        """
        if len(self._history) < self._min_samples:
            return {
                "status": "insufficient_data",
                "samples": len(self._history),
                "required": self._min_samples,
            }

        df = pd.DataFrame(self._history)

        # Build feature matrix
        available_features = [c for c in self.FEATURE_COLS if c in df.columns]
        X = df[available_features].fillna(0).values
        y = df["is_winner"].astype(int).values

        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import TimeSeriesSplit
            from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

            self.model = GradientBoostingClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=5,
                random_state=42,
            )

            # Time-aware cross-validation — scale inside each fold
            # to avoid validation-statistics leakage
            tscv = TimeSeriesSplit(n_splits=5)
            fold_scores, fold_brier, fold_auc = [], [], []
            for train_idx, val_idx in tscv.split(X):
                fold_scaler = StandardScaler()
                Xtr = fold_scaler.fit_transform(X[train_idx])
                Xval = fold_scaler.transform(X[val_idx])
                ytr, yval = y[train_idx], y[val_idx]
                self.model.fit(Xtr, ytr)
                proba = self.model.predict_proba(Xval)[:, 1]
                fold_scores.append(float((self.model.predict(Xval) == yval).mean()))
                fold_brier.append(float(brier_score_loss(yval, proba)))
                if len(set(yval)) > 1:
                    fold_auc.append(float(roc_auc_score(yval, proba)))

            # Fit final model on all data (scaler fitted only on training)
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            self._save_model()

            # Feature importance
            importances = dict(zip(available_features, self.model.feature_importances_))
            metrics = {
                "status": "trained",
                "samples": len(self._history),
                "cv_accuracy": float(np.mean(fold_scores)),
                "cv_std": float(np.std(fold_scores)),
                "cv_brier": float(np.mean(fold_brier)),
                "cv_auc": float(np.mean(fold_auc)) if fold_auc else None,
                "feature_importances": importances,
                "win_rate_actual": float(y.mean()),
            }
            logger.info(f"Model trained: accuracy={metrics['cv_accuracy']:.3f} brier={metrics['cv_brier']:.3f}")
            return metrics

        except ImportError:
            logger.error("scikit-learn not installed: pip install scikit-learn")
            return {"status": "error", "message": "scikit-learn not installed"}

    def predict_win_probability(
        self, features: Dict[str, Any]
    ) -> Optional[float]:
        """Predict probability of trade success."""
        if self.model is None or self.scaler is None:
            return None

        available = [c for c in self.FEATURE_COLS if c in features]
        if len(available) < 3:
            return None

        X = np.array([[features.get(c, 0) for c in self.FEATURE_COLS]])
        X_scaled = self.scaler.transform(X)
        proba = self.model.predict_proba(X_scaled)[0][1]
        return float(proba)

    def get_optimal_position_size(
        self,
        win_prob: float,
        avg_win: float = 2.0,
        avg_loss: float = 1.0,
    ) -> float:
        """Kelly criterion for optimal position sizing."""
        if win_prob <= 0 or avg_win <= 0 or avg_loss <= 0:
            return 0.0
        # Kelly fraction = (p * b - q) / b
        # where p = win prob, q = loss prob, b = win/loss ratio
        b = avg_win / avg_loss
        q = 1.0 - win_prob
        kelly = (win_prob * b - q) / b
        # Use half-Kelly for safety
        half_kelly = max(0.0, kelly * 0.5)
        # Cap at max position
        return min(half_kelly, trading_config.max_position_pct)

    # ── Sprint 38: Regression heads ───────────────────────────

    def train_regression(self) -> Dict[str, Any]:
        """Train regression models for R-multiple, MAE, hold-days.

        Complements the classification model by predicting the
        *magnitude* of expected outcomes, not just win/loss.
        """
        if len(self._history) < self._min_samples:
            return {"status": "insufficient_data"}

        df = pd.DataFrame(self._history)
        available = [
            c for c in self.FEATURE_COLS if c in df.columns
        ]
        X = df[available].fillna(0).values

        results: Dict[str, Any] = {"status": "trained"}
        try:
            from sklearn.ensemble import (
                GradientBoostingRegressor,
            )
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # R-multiple predictor
            if "r_multiple" in df.columns:
                y_r = df["r_multiple"].fillna(0).values
                model_r = GradientBoostingRegressor(
                    n_estimators=150, max_depth=3,
                    learning_rate=0.05, random_state=42,
                )
                model_r.fit(X_scaled, y_r)
                self._reg_r_model = model_r
                self._reg_scaler = scaler
                results["r_multiple_trained"] = True

            # MAE predictor (maximum adverse excursion)
            if "mae_pct" in df.columns:
                y_mae = df["mae_pct"].fillna(0).values
                model_mae = GradientBoostingRegressor(
                    n_estimators=150, max_depth=3,
                    learning_rate=0.05, random_state=42,
                )
                model_mae.fit(X_scaled, y_mae)
                self._reg_mae_model = model_mae
                results["mae_trained"] = True

            # Hold-time predictor
            if "hold_hours" in df.columns:
                y_hold = df["hold_hours"].fillna(0).values
                model_hold = GradientBoostingRegressor(
                    n_estimators=100, max_depth=3,
                    learning_rate=0.05, random_state=42,
                )
                model_hold.fit(X_scaled, y_hold)
                self._reg_hold_model = model_hold
                results["hold_days_trained"] = True

        except ImportError:
            results["status"] = "error"
            results["message"] = "scikit-learn not installed"
        return results

    def predict_r_multiple(
        self, features: Dict[str, Any],
    ) -> Optional[float]:
        """Predict expected R-multiple for a trade setup."""
        model = getattr(self, "_reg_r_model", None)
        scaler = getattr(self, "_reg_scaler", None)
        if model is None or scaler is None:
            return None
        X = np.array(
            [[features.get(c, 0) for c in self.FEATURE_COLS]]
        )
        return float(model.predict(scaler.transform(X))[0])

    def predict_mae(
        self, features: Dict[str, Any],
    ) -> Optional[float]:
        """Predict expected MAE (max adverse excursion %)."""
        model = getattr(self, "_reg_mae_model", None)
        scaler = getattr(self, "_reg_scaler", None)
        if model is None or scaler is None:
            return None
        X = np.array(
            [[features.get(c, 0) for c in self.FEATURE_COLS]]
        )
        return float(model.predict(scaler.transform(X))[0])

    def predict_hold_days(
        self, features: Dict[str, Any],
    ) -> Optional[float]:
        """Predict expected holding period in hours."""
        model = getattr(self, "_reg_hold_model", None)
        scaler = getattr(self, "_reg_scaler", None)
        if model is None or scaler is None:
            return None
        X = np.array(
            [[features.get(c, 0) for c in self.FEATURE_COLS]]
        )
        return float(model.predict(scaler.transform(X))[0])


# ---------------------------------------------------------------------------
# LLM Failure Analyst
# ---------------------------------------------------------------------------

class LLMFailureAnalyst:
    """
    Uses LLM to analyze losing trades and extract actionable patterns.
    
    - Groups losses by strategy, market regime, sector
    - Identifies common failure modes
    - Suggests parameter adjustments
    - Generates natural-language insights
    """

    ANALYSIS_PROMPT = """You are an expert quantitative trading analyst. Analyze these losing trades and provide actionable insights.

## Losing Trades Data
{trades_json}

## Analysis Required
1. **Common Failure Patterns**: What patterns do you see in these losses? (e.g., entering at wrong regime, RSI too high, volume too low)
2. **Strategy-Specific Issues**: For each strategy, what went wrong?
3. **Market Regime Mismatch**: Were trades taken in unsuitable market conditions?
4. **Risk Management Gaps**: Were stops too tight or too loose? Were position sizes appropriate?
5. **Actionable Recommendations**: List 3-5 specific parameter changes or rule additions.

Respond in JSON format:
{{
    "patterns": ["pattern1", "pattern2"],
    "strategy_issues": {{"strategy_name": "issue description"}},
    "regime_mismatches": ["mismatch1"],
    "risk_gaps": ["gap1"],
    "recommendations": [
        {{"action": "...", "parameter": "...", "current": "...", "suggested": "...", "rationale": "..."}}
    ],
    "summary": "One paragraph summary"
}}"""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is not None:
            return self._client

        if settings.openai_api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)
                return self._client
            except ImportError:
                pass

        if settings.azure_openai_endpoint:
            try:
                from openai import AsyncAzureOpenAI
                self._client = AsyncAzureOpenAI(
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                )
                return self._client
            except ImportError:
                pass

        return None

    async def analyze_failures(
        self, losing_trades: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze a batch of losing trades with LLM."""
        if not losing_trades:
            return None

        client = await self._get_client()
        if client is None:
            logger.warning("No LLM client configured for failure analysis")
            return None

        # Prepare trade data (limit to prevent token overflow)
        trades_subset = losing_trades[:50]
        trades_json = json.dumps(trades_subset, indent=2, default=str)

        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a quantitative trading analyst. Respond only in valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": self.ANALYSIS_PROMPT.format(trades_json=trades_json),
                    },
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            analysis = json.loads(content)
            logger.info(f"LLM failure analysis complete: {len(analysis.get('recommendations', []))} recommendations")
            return analysis

        except Exception as e:
            logger.error(f"LLM failure analysis error: {e}")
            return None


# ---------------------------------------------------------------------------
# Integrated Learning Loop
# ---------------------------------------------------------------------------

class TradeLearningLoop:
    """
    Complete learning loop that ties everything together.
    
    Flow:
    1. Record trade outcomes
    2. When enough data: train predictor
    3. Periodically: run LLM failure analysis
    4. Apply recommendations to strategy parameters
    5. Feed predictions back to signal pipeline
    """

    def __init__(self):
        self.predictor = TradeOutcomePredictor()
        self.analyst = LLMFailureAnalyst()
        self._outcomes: List[TradeOutcomeRecord] = []
        self._last_train_count = 0
        self._retrain_interval = 20  # retrain every 20 new trades
        self._last_analysis: Optional[Dict[str, Any]] = None
        self._load_persisted_outcomes()

    def record_outcome(self, record: TradeOutcomeRecord):
        """Record a trade outcome and trigger retraining if needed."""
        self._outcomes.append(record)
        self.predictor.add_outcome(record)

        # Auto-retrain
        new_since_train = len(self._outcomes) - self._last_train_count
        if new_since_train >= self._retrain_interval:
            metrics = self.predictor.train()
            self._last_train_count = len(self._outcomes)
            logger.info(f"Auto-retrained model: {metrics}")
            self._persist_outcomes()

    def predict_signal_quality(self, signal_features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict quality of a potential signal before execution."""
        win_prob = self.predictor.predict_win_probability(signal_features)
        if win_prob is None:
            return {"model_available": False}

        position_size = self.predictor.get_optimal_position_size(win_prob)
        return {
            "model_available": True,
            "win_probability": round(win_prob, 3),
            "recommended_position_pct": round(position_size * 100, 2),
            "signal_grade": (
                "A" if win_prob > 0.7
                else "B" if win_prob > 0.55
                else "C" if win_prob > 0.4
                else "D"
            ),
        }

    async def run_failure_analysis(self) -> Optional[Dict[str, Any]]:
        """Run LLM analysis on recent losing trades."""
        losers = [
            o.to_dict() for o in self._outcomes
            if not o.data["is_winner"]
        ]
        if len(losers) < 5:
            return None

        analysis = await self.analyst.analyze_failures(losers[-50:])
        if analysis:
            self._last_analysis = analysis
        return analysis

    # ── Sprint 29: calibration tracking ───────────────────

    def get_calibration_stats(
        self, n_bins: int = 5,
    ) -> Dict[str, Any]:
        """Compare predicted win probabilities to actual outcomes.

        Bins all predictions into ``n_bins`` buckets and computes
        the mean predicted probability vs actual win rate for each
        bucket.  Returns empty dict if no predictions yet.
        """
        if not self._outcomes or self.predictor.model is None:
            return {"calibrated": False, "reason": "no_model"}

        preds: List[Tuple[float, bool]] = []
        for o in self._outcomes:
            d = o.to_dict()
            features = {
                c: d.get(c, 0)
                for c in self.predictor.FEATURE_COLS
            }
            prob = self.predictor.predict_win_probability(features)
            if prob is not None:
                preds.append((prob, d["is_winner"]))

        if len(preds) < 10:
            return {
                "calibrated": False,
                "reason": "insufficient_predictions",
                "count": len(preds),
            }

        # Sort by predicted prob and bin
        preds.sort(key=lambda x: x[0])
        bin_size = max(1, len(preds) // n_bins)
        bins: List[Dict[str, Any]] = []
        for i in range(0, len(preds), bin_size):
            chunk = preds[i:i + bin_size]
            if not chunk:
                continue
            mean_pred = sum(p for p, _ in chunk) / len(chunk)
            actual_wr = sum(
                1 for _, w in chunk if w
            ) / len(chunk)
            bins.append({
                "predicted": round(mean_pred, 3),
                "actual": round(actual_wr, 3),
                "count": len(chunk),
            })

        # Brier-style calibration error
        cal_error = sum(
            abs(b["predicted"] - b["actual"]) * b["count"]
            for b in bins
        ) / len(preds)

        return {
            "calibrated": True,
            "bins": bins,
            "calibration_error": round(cal_error, 4),
            "total_predictions": len(preds),
        }

    def _persist_outcomes(self):
        """Save trade outcomes to JSON for persistence across restarts."""
        import json
        path = MODEL_DIR / "trade_outcomes.json"
        try:
            data = [o.to_dict() for o in self._outcomes]
            with open(path, "w") as f:
                json.dump(data, f, default=str)
            logger.info("Persisted %d trade outcomes to %s", len(data), path)
        except Exception as e:
            logger.warning("Outcome persistence error: %s", e)

    def _load_persisted_outcomes(self):
        """Load previously saved trade outcomes."""
        import json
        path = MODEL_DIR / "trade_outcomes.json"
        if not path.exists():
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            for d in data:
                # Sprint 29: preserve full context fields on
                # reload so model retraining has full feature set
                record = TradeOutcomeRecord(
                    trade_id=d.get("trade_id", ""),
                    ticker=d.get("ticker", ""),
                    direction=d.get("direction", "LONG"),
                    strategy=d.get("strategy", "unknown"),
                    entry_price=d.get("entry_price", 0),
                    exit_price=d.get("exit_price", 0),
                    entry_time=d.get("entry_time", ""),
                    exit_time=d.get("exit_time", ""),
                    pnl_pct=d.get("pnl_pct", 0),
                    confidence=d.get("confidence", 50),
                    horizon=d.get("horizon", "swing"),
                    market_regime=d.get("market_regime", ""),
                    vix_at_entry=d.get("vix_at_entry", 0.0),
                    rsi_at_entry=d.get("rsi_at_entry", 0.0),
                    adx_at_entry=d.get("adx_at_entry", 0.0),
                    relative_volume=d.get("relative_volume", 0.0),
                    distance_from_sma50=d.get(
                        "distance_from_sma50", 0.0,
                    ),
                    exit_reason=d.get("exit_reason", ""),
                    hold_hours=d.get("hold_hours", 0.0),
                )
                self._outcomes.append(record)
                self.predictor.add_outcome(record)
            logger.info("Loaded %d persisted trade outcomes", len(data))
        except Exception as e:
            logger.warning("Outcome load error: %s", e)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of learning loop performance."""
        if not self._outcomes:
            return {"total_trades": 0}

        wins = sum(1 for o in self._outcomes if o.data["is_winner"])
        total = len(self._outcomes)
        pnls = [o.data["pnl_pct"] for o in self._outcomes]

        # Strategy breakdown
        by_strategy: Dict[str, List[float]] = defaultdict(list)
        for o in self._outcomes:
            by_strategy[o.data["strategy"]].append(o.data["pnl_pct"])

        strategy_stats = {}
        for strat, pnl_list in by_strategy.items():
            w = sum(1 for p in pnl_list if p > 0)
            strategy_stats[strat] = {
                "trades": len(pnl_list),
                "win_rate": round(w / len(pnl_list) * 100, 1) if pnl_list else 0,
                "avg_pnl": round(np.mean(pnl_list), 2),
                "total_pnl": round(sum(pnl_list), 2),
            }

        return {
            "total_trades": total,
            "win_rate": round(wins / total * 100, 1),
            "avg_pnl": round(np.mean(pnls), 2),
            "total_pnl": round(sum(pnls), 2),
            "best_trade": round(max(pnls), 2),
            "worst_trade": round(min(pnls), 2),
            "sharpe_approx": round(np.mean(pnls) / np.std(pnls), 2) if np.std(pnls) > 0 else 0,
            "model_trained": self.predictor.model is not None,
            "last_analysis": self._last_analysis is not None,
            "strategy_breakdown": strategy_stats,
        }
