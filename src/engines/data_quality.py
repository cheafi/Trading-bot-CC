"""
TradingAI Bot — Data Quality Gates (v6 Pro Desk)

Runs BEFORE feature computation and signal generation.
If any critical feed is stale or corrupt, we suppress signals
rather than emit garbage.

Checks:
  • Freshness: each feed must be within its staleness threshold
  • Missing bars: gaps > 3 trading days → warning; OHLCV gap today → critical
  • Outlier detection: single-bar return > 30% → flag for review
  • Symbol mapping: if > 10% of universe has no features → critical
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.core.models import DataQualityReport

logger = logging.getLogger(__name__)


# ─── Freshness thresholds per feed ──────────────────────────────────
FRESHNESS_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "ohlcv": {
        "max_staleness_minutes": 15,
        "severity": "critical",
    },
    "features": {
        "max_staleness_minutes": 30,
        "severity": "critical",
    },
    "market_breadth": {
        "max_staleness_minutes": 60,
        "severity": "warning",
    },
    "news": {
        "max_staleness_minutes": 120,
        "severity": "warning",
    },
    "social": {
        "max_staleness_minutes": 240,
        "severity": "info",
    },
    "options": {
        "max_staleness_minutes": 60,
        "severity": "warning",
    },
}


def _make_report(
    feed: str,
    check: str,
    severity: str,
    passed: bool,
    details_text: str,
    affected: Optional[List[str]] = None,
) -> DataQualityReport:
    """Helper to construct a DataQualityReport with the v6 schema."""
    return DataQualityReport(
        check_time=datetime.utcnow(),
        feed_name=feed,
        check_type=check,
        passed=passed,
        severity=severity,
        details={"message": details_text},
        affected_tickers=affected or [],
    )


class DataQualityGate:
    """
    Run all data-quality checks and return a go/no-go decision.

    Usage::

        gate = DataQualityGate()
        passed, reports = gate.run_all_checks(market_data)
        if not passed:
            # suppress signals — data not trustworthy
            ...
    """

    def __init__(
        self,
        freshness_overrides: Optional[Dict[str, int]] = None,
    ):
        self.thresholds = dict(FRESHNESS_THRESHOLDS)
        if freshness_overrides:
            for feed, minutes in freshness_overrides.items():
                if feed in self.thresholds:
                    self.thresholds[feed][
                        "max_staleness_minutes"
                    ] = minutes

    # ── public API ──────────────────────────────────────────────

    def run_all_checks(
        self,
        market_data: Dict[str, Any],
        features_df: Any = None,
        universe: Optional[List[str]] = None,
    ) -> Tuple[bool, List[DataQualityReport]]:
        """
        Run every check and return *(all_critical_passed, reports)*.

        Parameters
        ----------
        market_data : dict
            Must include ``feed_timestamps`` mapping feed names to
            ISO-8601 or ``datetime`` objects, plus optional
            ``ohlcv_gap_days``, ``outlier_tickers``,
            ``universe_coverage_pct``, etc.
        features_df : DataFrame or None
            Currently unused; reserved for outlier detection.
        universe : list[str] or None
            Full ticker list — used for coverage check.
        """
        reports: List[DataQualityReport] = []

        reports.extend(self._check_freshness(market_data))
        reports.extend(self._check_missing_bars(market_data))
        reports.extend(self._check_outliers(market_data))
        reports.extend(
            self._check_symbol_mapping(market_data, universe)
        )

        all_critical_passed = all(
            not (r.severity == "critical" and not r.passed)
            for r in reports
        )

        if not all_critical_passed:
            critical = [
                r for r in reports
                if r.severity == "critical" and not r.passed
            ]
            logger.warning(
                "Data quality CRITICAL failures: %s",
                "; ".join(
                    f"{r.feed_name}/{r.check_type}" for r in critical
                ),
            )
        else:
            logger.info(
                "Data quality OK — %d reports, 0 critical",
                len(reports),
            )

        return all_critical_passed, reports

    def get_status_summary(
        self, reports: List[DataQualityReport]
    ) -> Dict[str, Any]:
        """Human-readable summary for dashboards / Discord."""
        critical = [
            r for r in reports
            if r.severity == "critical" and not r.passed
        ]
        warnings = [
            r for r in reports
            if r.severity == "warning" and not r.passed
        ]
        overall = (
            "🔴 CRITICAL"
            if critical
            else "🟡 WARNING" if warnings else "🟢 OK"
        )
        return {
            "overall": overall,
            "critical": [
                f"{r.feed_name}: {r.details}" for r in critical
            ],
            "warnings": [
                f"{r.feed_name}: {r.details}" for r in warnings
            ],
            "total_checks": len(reports),
        }

    # ── individual checks ───────────────────────────────────────

    def _check_freshness(
        self, market_data: Dict[str, Any]
    ) -> List[DataQualityReport]:
        """Check each feed timestamp vs its staleness threshold."""
        reports: List[DataQualityReport] = []
        feed_ts = market_data.get("feed_timestamps", {})
        now = datetime.utcnow()

        for feed, cfg in self.thresholds.items():
            ts_raw = feed_ts.get(feed)
            if ts_raw is None:
                reports.append(
                    _make_report(
                        feed=feed,
                        check="freshness",
                        severity=cfg["severity"],
                        passed=False,
                        details_text=(
                            f"No timestamp for {feed} — "
                            "cannot verify freshness"
                        ),
                    )
                )
                continue

            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(
                        ts_raw.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except ValueError:
                    reports.append(
                        _make_report(
                            feed=feed,
                            check="freshness",
                            severity="warning",
                            passed=False,
                            details_text=(
                                f"Unparseable timestamp: {ts_raw}"
                            ),
                        )
                    )
                    continue
            elif isinstance(ts_raw, datetime):
                ts = ts_raw.replace(tzinfo=None)
            else:
                continue

            age = now - ts
            limit = timedelta(
                minutes=cfg["max_staleness_minutes"]
            )
            if age > limit:
                reports.append(
                    _make_report(
                        feed=feed,
                        check="freshness",
                        severity=cfg["severity"],
                        passed=False,
                        details_text=(
                            f"{feed} stale by "
                            f"{int(age.total_seconds() // 60)}min "
                            f"(limit "
                            f"{cfg['max_staleness_minutes']}min)"
                        ),
                    )
                )

        return reports

    def _check_missing_bars(
        self, market_data: Dict[str, Any]
    ) -> List[DataQualityReport]:
        """Flag if OHLCV data has gaps > 3 trading days."""
        reports: List[DataQualityReport] = []

        gap_days = market_data.get("ohlcv_gap_days", 0)
        if gap_days > 3:
            reports.append(
                _make_report(
                    feed="ohlcv",
                    check="missing_bars",
                    severity="critical",
                    passed=False,
                    details_text=(
                        f"OHLCV has {gap_days}-day gap "
                        "(> 3 trading days)"
                    ),
                )
            )
        elif gap_days > 1:
            reports.append(
                _make_report(
                    feed="ohlcv",
                    check="missing_bars",
                    severity="warning",
                    passed=False,
                    details_text=(
                        f"OHLCV has {gap_days}-day gap"
                    ),
                )
            )

        return reports

    def _check_outliers(
        self, market_data: Dict[str, Any]
    ) -> List[DataQualityReport]:
        """Flag single-bar returns > 30% as possible data errors."""
        reports: List[DataQualityReport] = []

        outlier_tickers = market_data.get(
            "outlier_tickers", []
        )
        if outlier_tickers:
            names = []
            for item in outlier_tickers:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict):
                    names.append(item.get("ticker", "?"))
            reports.append(
                _make_report(
                    feed="ohlcv",
                    check="outlier",
                    severity="warning",
                    passed=True,  # warning only
                    details_text=(
                        f"{len(names)} ticker(s) with >30% "
                        "single-bar move — possible bad print"
                    ),
                    affected=names[:20],
                )
            )

        return reports

    def _check_symbol_mapping(
        self,
        market_data: Dict[str, Any],
        universe: Optional[List[str]] = None,
    ) -> List[DataQualityReport]:
        """
        If > 10% of the universe has no features row,
        something is wrong with ingestion.
        """
        reports: List[DataQualityReport] = []

        coverage_pct = market_data.get("universe_coverage_pct")
        if coverage_pct is not None and coverage_pct < 90:
            sev = "critical" if coverage_pct < 80 else "warning"
            reports.append(
                _make_report(
                    feed="features",
                    check="symbol_mapping",
                    severity=sev,
                    passed=coverage_pct >= 80,
                    details_text=(
                        f"Only {coverage_pct:.0f}% of universe "
                        "has feature data"
                    ),
                )
            )

        return reports
