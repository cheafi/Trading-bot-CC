"""Alpha manifest + 13F XML parse unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.services.alpha_manifest import ensure_manifest_file, load_manifest, manifest_summary
from src.services.alpha_zoo_bench import bench_manifest_on_history
from src.services.filing_13f_holdings import _parse_13f_positions, _normalize_holdings


_SAMPLE_XML = """<?xml version="1.0"?>
<informationTable>
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <cusip>037833100</cusip>
    <value>1000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>5000</sshPrnamt>
    </shrsOrPrnAmt>
  </infoTable>
</informationTable>
"""


def test_manifest_has_478_entries(tmp_path, monkeypatch) -> None:
    from src.services import alpha_manifest as am

    monkeypatch.setattr(am, "_MANIFEST_PATH", tmp_path / "alpha_manifest.json")
    ensure_manifest_file()
    m = load_manifest(limit=478)
    assert m["total"] == 478
    assert len(m["alphas"]) == 478
    assert manifest_summary()["total_alphas"] == 478


def test_bench_manifest_synthetic() -> None:
    n = 200
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = np.cumsum(np.random.randn(n)) + 100
    df = pd.DataFrame(
        {"Close": close, "Open": close, "High": close + 1, "Low": close - 1, "Volume": 1e6},
        index=idx,
    )
    out = bench_manifest_on_history(df, compute_limit=15, manifest_limit=478)
    assert out["ok"] is True
    assert out["computed_count"] == 15
    assert "summary" in out


def test_parse_13f_xml_sample() -> None:
    rows = _parse_13f_positions(_SAMPLE_XML)
    assert len(rows) >= 1
    assert any("APPLE" in str(r.get("issuer", "")).upper() for r in rows)
    assert rows[0].get("shares") == 5000.0


_NAMESPACED_XML = """<?xml version="1.0"?>
<n1:informationTable xmlns:n1="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <n1:infoTable>
    <n1:nameOfIssuer>MICROSOFT CORP</n1:nameOfIssuer>
    <n1:cusip>594918104</n1:cusip>
    <n1:value>2000</n1:value>
    <n1:shrsOrPrnAmt>
      <n1:sshPrnamt>1200</n1:sshPrnamt>
    </n1:shrsOrPrnAmt>
  </n1:infoTable>
</n1:informationTable>
"""


def test_canonical_alpha_k101_and_gtja() -> None:
    from src.services.alpha_formulas import canonical_formula_for_id, canonical_pack_stats

    assert canonical_formula_for_id("k101_001") == "log_momentum"
    assert canonical_formula_for_id("gtja_001") == "rank_roc"
    assert canonical_formula_for_id("acad_001") == "roc"
    assert canonical_formula_for_id("pit_001") == "roc"
    stats = canonical_pack_stats()
    assert stats["canonical_count"] == 478
    assert stats["manifest_total"] == 478


def test_canonical_alpha_qlib_001() -> None:
    import numpy as np
    import pandas as pd

    from src.services.alpha_formulas import canonical_formula_for_id, compute_canonical_factor
    from src.services.alpha_zoo_bench import bench_manifest_on_history

    assert canonical_formula_for_id("qlib_001") == "roc"
    n = 120
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = np.cumsum(np.random.randn(n)) + 50
    df = pd.DataFrame({"Close": close}, index=idx)
    out = bench_manifest_on_history(df, compute_limit=5, manifest_limit=5)
    assert out["ok"] is True
    first = out["results"][0]
    assert first.get("canonical") is True
    assert first.get("formula") == "roc"
    factor = compute_canonical_factor(
        df.rename(columns={"Close": "close"}), "roc", 10
    )
    assert len(factor.dropna()) > 10


def test_parse_13f_xml_namespaced() -> None:
    rows = _parse_13f_positions(_NAMESPACED_XML)
    assert len(rows) == 1
    assert "MICROSOFT" in rows[0]["issuer"].upper()
    assert rows[0]["shares"] == 1200.0
