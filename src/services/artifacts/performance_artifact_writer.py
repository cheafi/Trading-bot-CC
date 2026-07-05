"""
Performance Artifact Writer
============================

Writes immutable artifact bundles for the Performance Lab surface.
Each generation produces:
  - ``{artifact_id}.json``  — full metrics + provenance
  - ``{artifact_id}.csv``   — trade ledger / monthly return table
  - ``{artifact_id}.png``   — equity curve + drawdown chart
  - ``{artifact_id}.md``    — executive summary

Artifacts live under ``DATA_DIR/artifacts/performance/``.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default output root — can be overridden via constructor
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class PerformanceArtifactWriter:
    """Write immutable performance artifacts (json / csv / png / md)."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.base = (data_dir or _DEFAULT_DATA_DIR) / "artifacts" / "performance"
        self.base.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Write a full artifact bundle.

        Parameters
        ----------
        payload : dict
            The performance-lab response dict.  Must contain at minimum
            ``summary``, ``equity_curve``, ``monthly_returns``, ``trust``.

        Returns
        -------
        dict
            ``{"artifact_id": ..., "artifact_paths": {...}, "generated_at": ...}``
        """
        artifact_id = f"perf-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        ts = datetime.now(timezone.utc).isoformat()

        paths: Dict[str, str] = {}

        # ── JSON ──────────────────────────────────────────────
        json_path = self._json(artifact_id, payload, ts)
        paths["json"] = str(json_path)

        # ── CSV ───────────────────────────────────────────────
        csv_path = self._csv(artifact_id, payload)
        paths["csv"] = str(csv_path)

        # ── PNG (best-effort) ─────────────────────────────────
        png_path = self._png(artifact_id, payload)
        if png_path:
            paths["png"] = str(png_path)

        # ── Markdown ──────────────────────────────────────────
        md_path = self._md(artifact_id, payload, ts)
        paths["md"] = str(md_path)

        return {
            "artifact_id": artifact_id,
            "artifact_paths": paths,
            "generated_at": ts,
        }

    # ------------------------------------------------------------------
    # Internal writers
    # ------------------------------------------------------------------

    def _json(
        self, aid: str, payload: Dict[str, Any], ts: str,
    ) -> Path:
        out = self.base / f"{aid}.json"
        blob = {
            "artifact_id": aid,
            "generated_at": ts,
            "version": "1.0",
            **payload,
        }
        out.write_text(json.dumps(blob, indent=2, default=str), encoding="utf-8")
        logger.info("artifact:json → %s", out)
        return out

    def _csv(self, aid: str, payload: Dict[str, Any]) -> Path:
        out = self.base / f"{aid}.csv"

        summary = payload.get("summary", {})
        eq = payload.get("equity_curve", {})
        monthly = payload.get("monthly_returns", {})

        buf = io.StringIO()
        w = csv.writer(buf)

        # Section 1 — KPI summary
        w.writerow(["# KPI Summary"])
        w.writerow(["metric", "value"])
        for k, v in summary.items():
            w.writerow([k, v])
        w.writerow([])

        # Section 2 — equity curve
        dates = eq.get("dates", [])
        values = eq.get("values", [])
        benchmark = eq.get("benchmark", [])
        w.writerow(["# Equity Curve"])
        w.writerow(["date", "portfolio", "benchmark"])
        for i, d in enumerate(dates):
            bm = benchmark[i] if i < len(benchmark) else ""
            val = values[i] if i < len(values) else ""
            w.writerow([d, val, bm])
        w.writerow([])

        # Section 3 — monthly returns
        w.writerow(["# Monthly Returns"])
        w.writerow(["year", "month", "return_pct"])
        for year, months in monthly.items():
            for month, ret in months.items():
                w.writerow([year, month, ret])

        out.write_text(buf.getvalue(), encoding="utf-8")
        logger.info("artifact:csv → %s", out)
        return out

    def _png(self, aid: str, payload: Dict[str, Any]) -> Optional[Path]:
        """Best-effort equity + drawdown chart."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError:
            logger.debug("matplotlib not installed — skipping PNG artifact")
            return None

        eq = payload.get("equity_curve", {})
        dates = eq.get("dates", [])
        values = eq.get("values", [])
        benchmark = eq.get("benchmark", [])
        trust = payload.get("trust", {})
        mode = trust.get("mode", "UNKNOWN")

        if not values or len(values) < 2:
            return None

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(10, 6), height_ratios=[3, 1],
            sharex=True, gridspec_kw={"hspace": 0.08},
        )

        x = list(range(len(values)))
        ax1.plot(x, values, label="Portfolio", linewidth=1.5, color="#2563eb")
        if benchmark and len(benchmark) == len(values):
            ax1.plot(x, benchmark, label="SPY", linewidth=1, color="#94a3b8", linestyle="--")
        ax1.set_ylabel("Value (indexed 100)")
        ax1.legend(loc="upper left", fontsize=8)
        ax1.set_title(f"Performance Lab — {mode}", fontsize=10)
        ax1.grid(alpha=0.3)

        # Drawdown subplot
        arr = np.array(values, dtype=float)
        peak = np.maximum.accumulate(arr)
        dd = (arr - peak) / peak * 100
        ax2.fill_between(x, dd, 0, alpha=0.35, color="#ef4444")
        ax2.set_ylabel("Drawdown %")
        ax2.set_xlabel("Month")
        ax2.grid(alpha=0.3)

        # Use date labels if available
        if dates and len(dates) == len(values):
            step = max(1, len(dates) // 8)
            ax2.set_xticks(x[::step])
            ax2.set_xticklabels(
                [d[:7] for d in dates[::step]],
                rotation=45, fontsize=7,
            )

        out = self.base / f"{aid}.png"
        fig.savefig(out, dpi=120, bbox_inches="tight")
        plt.close(fig)
        logger.info("artifact:png → %s", out)
        return out

    def _md(
        self, aid: str, payload: Dict[str, Any], ts: str,
    ) -> Path:
        out = self.base / f"{aid}.md"

        s = payload.get("summary", {})
        trust = payload.get("trust", {})
        mode = trust.get("mode", "UNKNOWN")
        source = trust.get("source", "unknown")
        sample = trust.get("sample_size", 0)
        warning = trust.get("data_warning")

        lines = [
            f"# Performance Lab Report",
            f"",
            f"**Artifact ID:** `{aid}`  ",
            f"**Generated:** {ts}  ",
            f"**Mode:** {mode} | **Source:** {source} | **Sample:** {sample}  ",
        ]
        if warning:
            lines.append(f"")
            lines.append(f"> ⚠️ {warning}")

        lines += [
            "",
            "## KPI Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Annual Return | {s.get('annual_return', 'N/A')}% |",
            f"| Alpha | {s.get('alpha', 'N/A')}% |",
            f"| Beta | {s.get('beta', 'N/A')} |",
            f"| Sharpe | {s.get('sharpe', 'N/A')} |",
            f"| Sortino | {s.get('sortino', 'N/A')} |",
            f"| Calmar | {s.get('calmar', 'N/A')} |",
            f"| Max Drawdown | {s.get('max_drawdown', 'N/A')}% |",
            f"| Win Rate | {s.get('win_rate', 'N/A')} |",
            f"| Profit Factor | {s.get('profit_factor', 'N/A')} |",
            f"| VaR 95% | {s.get('var_95', 'N/A')}% |",
            f"| CVaR 95% | {s.get('cvar_95', 'N/A')}% |",
            "",
            "---",
            f"*Trust: {mode} / {source} / n={sample}*",
        ]

        out.write_text("\n".join(lines), encoding="utf-8")
        logger.info("artifact:md → %s", out)
        return out
