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
"""
import asyncio
import json
import logging
import pickle
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
        "relative_volume", "distance_from_sma50", "hold_hours",
        "max_adverse_excursion",
    ]

    def __init__(self):
        self.model = None
        self.scaler = None
        self._model_path = MODEL_DIR / "trade_outcome_model.pkl"
        self._history: List[Dict[str, Any]] = []
        self._min_samples = 30  # minimum trades before training
        self._load_model()

    def _load_model(self):
        if self._model_path.exists():
            try:
                with open(self._model_path, "rb") as f:
                    saved = pickle.load(f)
                self.model = saved.get("model")
                self.scaler = saved.get("scaler")
                logger.info("Loaded trade outcome model")
            except Exception as e:
                logger.warning(f"Could not load model: {e}")

    def _save_model(self):
        try:
            with open(self._model_path, "wb") as f:
                pickle.dump({"model": self.model, "scaler": self.scaler}, f)
            logger.info("Saved trade outcome model")
        except Exception as e:
            logger.error(f"Could not save model: {e}")

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
            from sklearn.model_selection import cross_val_score

            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            self.model = GradientBoostingClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=5,
                random_state=42,
            )

            # Cross-validation
            scores = cross_val_score(self.model, X_scaled, y, cv=5, scoring="accuracy")

            # Fit on all data
            self.model.fit(X_scaled, y)
            self._save_model()

            # Feature importance
            importances = dict(zip(available_features, self.model.feature_importances_))

            metrics = {
                "status": "trained",
                "samples": len(self._history),
                "cv_accuracy": float(np.mean(scores)),
                "cv_std": float(np.std(scores)),
                "feature_importances": importances,
                "win_rate_actual": float(y.mean()),
            }
            logger.info(f"Model trained: accuracy={metrics['cv_accuracy']:.3f}")
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
