"""
Unified Research Artifact Writer
==================================

Standard artifact output for all v7 research surfaces:
  - compare-overlay
  - options-screen
  - strategy-portfolio-lab

Each run produces: json / csv / md (PNG optional via subclass).
Artifacts are immutable, keyed by ``{surface}-{timestamp}-{uuid}``.

Also provides an artifact registry for replay via
``/api/v7/research/artifacts/{artifact_id}``.
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

_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class ResearchArtifactWriter:
    """Unified artifact writer for v7 research surfaces."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.base = (
            (data_dir or _DEFAULT_DATA_DIR) / "artifacts" / "research"
        )
        self.base.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        surface: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Write an immutable artifact bundle.

        Parameters
        ----------
        surface : str
            Surface name: "compare-overlay", "options-screen",
            "strategy-portfolio-lab".
        payload : dict
            The endpoint response dict.

        Returns
        -------
        dict with artifact_id, artifact_paths, generated_at
        """
        ts = datetime.now(timezone.utc)
        artifact_id = (
            f"{surface}-"
            f"{ts.strftime('%Y%m%d-%H%M%S')}-"
            f"{uuid.uuid4().hex[:8]}"
        )
        ts_iso = ts.isoformat()
        paths: Dict[str, str] = {}

        # JSON
        json_path = self._write_json(artifact_id, payload, ts_iso)
        paths["json"] = str(json_path)

        # CSV
        csv_path = self._write_csv(
            artifact_id, surface, payload,
        )
        paths["csv"] = str(csv_path)

        # Markdown
        md_path = self._write_md(
            artifact_id, surface, payload, ts_iso,
        )
        paths["md"] = str(md_path)

        # Register in index
        self._update_index(artifact_id, surface, ts_iso, paths)

        return {
            "artifact_id": artifact_id,
            "artifact_paths": paths,
            "generated_at": ts_iso,
        }

    def load(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Load artifact by ID for replay."""
        json_path = self.base / f"{artifact_id}.json"
        if not json_path.exists():
            return None
        return json.loads(json_path.read_text(encoding="utf-8"))

    def list_artifacts(
        self,
        surface: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List recent artifacts, optionally filtered by surface."""
        index_path = self.base / "_index.json"
        if not index_path.exists():
            return []

        entries = json.loads(
            index_path.read_text(encoding="utf-8"),
        )

        if surface:
            entries = [
                e for e in entries if e.get("surface") == surface
            ]

        return sorted(
            entries,
            key=lambda e: e.get("generated_at", ""),
            reverse=True,
        )[:limit]

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def _write_json(
        self, aid: str, payload: Dict, ts: str,
    ) -> Path:
        out = self.base / f"{aid}.json"
        blob = {
            "artifact_id": aid,
            "generated_at": ts,
            "version": "1.0",
            **payload,
        }
        out.write_text(
            json.dumps(blob, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("artifact:json → %s", out)
        return out

    def _write_csv(
        self, aid: str, surface: str, payload: Dict,
    ) -> Path:
        out = self.base / f"{aid}.csv"
        buf = io.StringIO()
        w = csv.writer(buf)

        if surface == "compare-overlay":
            self._csv_compare(w, payload)
        elif surface == "options-screen":
            self._csv_options(w, payload)
        elif surface == "strategy-portfolio-lab":
            self._csv_strategy(w, payload)
        else:
            w.writerow(["key", "value"])
            for k, v in payload.items():
                if isinstance(v, (str, int, float)):
                    w.writerow([k, v])

        out.write_text(buf.getvalue(), encoding="utf-8")
        logger.info("artifact:csv → %s", out)
        return out

    def _write_md(
        self, aid: str, surface: str, payload: Dict, ts: str,
    ) -> Path:
        out = self.base / f"{aid}.md"
        trust = payload.get("trust", {})
        mode = trust.get("mode", "UNKNOWN")

        lines = [
            f"# Research Artifact: {surface}",
            "",
            f"**ID:** `{aid}`  ",
            f"**Generated:** {ts}  ",
            f"**Mode:** {mode}  ",
            "",
        ]

        if surface == "compare-overlay":
            lines += self._md_compare(payload)
        elif surface == "options-screen":
            lines += self._md_options(payload)
        elif surface == "strategy-portfolio-lab":
            lines += self._md_strategy(payload)

        lines += [
            "",
            "---",
            f"*Trust: {mode} / {trust.get('source', 'N/A')}*",
        ]

        out.write_text("\n".join(lines), encoding="utf-8")
        logger.info("artifact:md → %s", out)
        return out

    def _update_index(
        self,
        aid: str,
        surface: str,
        ts: str,
        paths: Dict[str, str],
    ) -> None:
        index_path = self.base / "_index.json"
        entries: List[Dict] = []
        if index_path.exists():
            try:
                entries = json.loads(
                    index_path.read_text(encoding="utf-8"),
                )
            except Exception:
                entries = []

        entries.append({
            "artifact_id": aid,
            "surface": surface,
            "generated_at": ts,
            "paths": paths,
        })

        # Keep last 200
        entries = entries[-200:]
        index_path.write_text(
            json.dumps(entries, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Surface-specific CSV formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _csv_compare(w: Any, p: Dict) -> None:
        w.writerow(["# Compare Overlay"])
        w.writerow(["ticker", "stat", "value"])
        for sym, stats in p.get("stats", {}).items():
            for k, v in stats.items():
                w.writerow([sym, k, v])

    @staticmethod
    def _csv_options(w: Any, p: Dict) -> None:
        w.writerow(["# Options Screen"])
        w.writerow([
            "rank", "strike", "dte", "type", "delta",
            "mid", "oi", "spread_pct", "ev", "liquidity_score",
        ])
        for c in p.get("contracts", []):
            w.writerow([
                c.get("rank"), c.get("strike"), c.get("dte"),
                c.get("type"), c.get("delta"), c.get("mid"),
                c.get("oi"), c.get("spread_pct"), c.get("ev"),
                c.get("liquidity_score"),
            ])

    @staticmethod
    def _csv_strategy(w: Any, p: Dict) -> None:
        w.writerow(["# Strategy Portfolio Lab"])
        w.writerow(["objective", "strategy", "weight"])
        for opt in p.get("optimizations", []):
            obj = opt.get("objective", "")
            for s, wt in opt.get("weights", {}).items():
                w.writerow([obj, s, wt])

    # ------------------------------------------------------------------
    # Surface-specific Markdown formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _md_compare(p: Dict) -> List[str]:
        tickers = p.get("tickers", [])
        lines = [
            "## Compare Overlay",
            "",
            f"**Tickers:** {', '.join(tickers)}  ",
            f"**Period:** {p.get('period', 'N/A')}  ",
            "",
            "| Ticker | Total Return | Sharpe | Max DD |",
            "|--------|-------------|--------|--------|",
        ]
        for sym, stats in p.get("stats", {}).items():
            lines.append(
                f"| {sym} "
                f"| {stats.get('total_return', 'N/A')}% "
                f"| {stats.get('sharpe', 'N/A')} "
                f"| {stats.get('max_drawdown', stats.get('max_dd', 'N/A'))}% |"
            )
        return lines

    @staticmethod
    def _md_options(p: Dict) -> List[str]:
        lines = [
            "## Options Screen",
            "",
            f"**Ticker:** {p.get('ticker', 'N/A')}  ",
            f"**Spot:** ${p.get('spot_price', 0)}  ",
            f"**Expression:** {p.get('expression_decision', 'N/A')}  ",
            "",
        ]
        warnings = p.get("warnings", [])
        if warnings:
            for w in warnings:
                lines.append(f"> {w}")
            lines.append("")

        lines += [
            "| Rank | Strike | DTE | Delta | Mid | OI | EV |",
            "|------|--------|-----|-------|-----|----|----|",
        ]
        for c in p.get("contracts", [])[:10]:
            lines.append(
                f"| {c.get('rank')} "
                f"| {c.get('strike')} "
                f"| {c.get('dte')} "
                f"| {c.get('delta')} "
                f"| {c.get('mid')} "
                f"| {c.get('oi')} "
                f"| {c.get('ev')} |"
            )
        return lines

    @staticmethod
    def _md_strategy(p: Dict) -> List[str]:
        lines = [
            "## Strategy Portfolio Lab",
            "",
            f"**Strategies:** {', '.join(p.get('strategies', []))}  ",
            "",
        ]
        for opt in p.get("optimizations", []):
            lines.append(f"### {opt.get('objective', '')}")
            lines.append("")
            lines.append("| Strategy | Weight |")
            lines.append("|----------|--------|")
            for s, w in opt.get("weights", {}).items():
                lines.append(f"| {s} | {w:.1%} |")
            lines.append(
                f"\nSharpe: {opt.get('sharpe', 'N/A')} | "
                f"Return: {opt.get('expected_return_pct', 'N/A')}% | "
                f"DD: {opt.get('max_drawdown_pct', 'N/A')}%\n"
            )
        return lines
