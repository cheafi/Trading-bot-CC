"""13F information table parse — share-level QoQ for one manager CIK (read-only SEC)."""

from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.services.filing_13f_cusip import resolve_ticker_from_cusip
from src.services.research_safety import sanitize_research_payload

logger = logging.getLogger(__name__)

_UA = os.environ.get(
    "SEC_USER_AGENT",
    "CC-MarketIntelligence support@example.com",
)


def _cik_pad(cik: str) -> str:
    return f"{int(str(cik).strip()):010d}"


async def _get_submissions(cik: str) -> Dict[str, Any]:
    url = f"https://data.sec.gov/submissions/CIK{_cik_pad(cik)}.json"
    headers = {"User-Agent": _UA, "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _recent_13f_accessions(submissions: Dict[str, Any], *, limit: int = 2) -> List[str]:
    recent = submissions.get("filings", {}).get("recent") or {}
    forms = recent.get("form") or []
    accessions = recent.get("accessionNumber") or []
    out: List[str] = []
    for form, acc in zip(forms, accessions):
        if str(form).upper().startswith("13F"):
            out.append(str(acc))
        if len(out) >= limit:
            break
    return out


async def _fetch_filing_xml(cik: str, accession: str) -> Optional[str]:
    cik_int = str(int(cik))
    acc_nodash = accession.replace("-", "")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/index.json"
    headers = {"User-Agent": _UA}
    async with httpx.AsyncClient(timeout=25.0) as client:
        idx = await client.get(index_url, headers=headers)
        if idx.status_code != 200:
            return None
        data = idx.json()
        items = data.get("directory", {}).get("item") or []
        xml_name = None
        candidates: List[str] = []
        for it in items:
            name = str(it.get("name") or "")
            if name.lower().endswith(".xml"):
                candidates.append(name)
        for name in candidates:
            low = name.lower()
            if "infotable" in low or "informationtable" in low:
                xml_name = name
                break
        if not xml_name:
            for name in candidates:
                if "primary" not in name.lower():
                    xml_name = name
                    break
        if not xml_name and candidates:
            xml_name = candidates[0]
        if not xml_name:
            return None
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{xml_name}"
        doc = await client.get(doc_url, headers=headers)
        if doc.status_code != 200:
            return None
        return doc.text


def _local_tag(tag: str) -> str:
    return tag.split("}")[-1].lower() if "}" in tag else tag.lower()


def _find_text(elem, local_name: str) -> str:
    for child in elem.iter():
        if _local_tag(child.tag) == local_name:
            val = (child.text or "").strip()
            if val:
                return val
    return ""


def _parse_13f_positions(xml_text: str) -> List[Dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows: List[Dict[str, Any]] = []
    for elem in root.iter():
        if _local_tag(elem.tag) != "infotable":
            continue
        row: Dict[str, Any] = {}
        for child in elem.iter():
            if child is elem:
                continue
            key = _local_tag(child.tag)
            val = (child.text or "").strip()
            if val and key not in row:
                row[key] = val
        if not row.get("nameofissuer"):
            t = _find_text(elem, "nameofissuer")
            if t:
                row["nameofissuer"] = t
        if not row.get("sshprnamt"):
            t = _find_text(elem, "sshprnamt")
            if t:
                row["sshprnamt"] = t
        if not row.get("sshprnamt"):
            for nested in ("shrsorprnamt", "shrsOrPrnAmt"):
                t = _find_text(elem, nested)
                if t:
                    row["sshprnamt"] = t
                    break
        if row:
            rows.append(row)
    return _normalize_holdings(rows) if rows else []


def _normalize_holdings(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in raw_rows:
        issuer = r.get("nameofissuer") or r.get("nameOfIssuer") or r.get("issuer")
        shares_raw = r.get("sshprnamt") or r.get("shrsorprnamt")
        if not shares_raw and isinstance(r.get("shrsorprnamt"), str):
            shares_raw = r.get("shrsorprnamt")
        try:
            shares = float(str(shares_raw or "0").replace(",", ""))
        except ValueError:
            shares = 0.0
        try:
            value_k = float(str(r.get("value") or "0").replace(",", ""))
        except ValueError:
            value_k = 0.0
        cusip = str(r.get("cusip") or "").strip()
        issuer_s = str(issuer or "")[:80]
        ticker = resolve_ticker_from_cusip(cusip, issuer=issuer_s)
        out.append(
            {
                "issuer": issuer_s,
                "cusip": cusip,
                "ticker": ticker,
                "shares": shares,
                "value_usd_thousands": value_k,
            }
        )
    return out


def _match_ticker_in_issuer(issuer: str, ticker: str) -> bool:
    t = ticker.upper()
    name = issuer.upper()
    if t in name.split():
        return True
    return re.search(rf"\b{re.escape(t)}\b", name) is not None


def _diff_holdings(
    current: List[Dict[str, Any]],
    prior: List[Dict[str, Any]],
    ticker: str,
) -> Dict[str, Any]:
    def index(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        m: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = row.get("cusip") or row.get("issuer")
            if key:
                m[str(key)] = row
        return m

    cur = index(current)
    prev = index(prior)
    ticker_rows: List[Dict[str, Any]] = []
    for row in current:
        if _match_ticker_in_issuer(str(row.get("issuer") or ""), ticker):
            ticker_rows.append(row)
    all_keys = set(cur) | set(prev)
    deltas: List[Dict[str, Any]] = []
    for key in list(all_keys)[:500]:
        a = cur.get(key)
        b = prev.get(key)
        sh_a = float((a or {}).get("shares") or 0)
        sh_b = float((b or {}).get("shares") or 0)
        if sh_a == sh_b:
            continue
        deltas.append(
            {
                "cusip": key if len(key) == 9 else (a or b or {}).get("cusip"),
                "issuer": (a or b or {}).get("issuer"),
                "shares_current": sh_a,
                "shares_prior": sh_b,
                "share_delta": round(sh_a - sh_b, 2),
            }
        )
    deltas.sort(key=lambda x: abs(x.get("share_delta") or 0), reverse=True)
    return {
        "ticker_matches_in_latest": ticker_rows[:5],
        "position_deltas": deltas[:25],
        "delta_count": len(deltas),
    }


async def fetch_13f_holdings_qoq(
    *,
    cik: str,
    ticker: str,
) -> Dict[str, Any]:
    """Share-level QoQ for one manager — SEC EDGAR 13F XML (two recent filings)."""
    try:
        subs = await _get_submissions(cik)
        accessions = _recent_13f_accessions(subs, limit=2)
        if len(accessions) < 2:
            return sanitize_research_payload(
                {
                    "ok": False,
                    "cik": cik,
                    "reason": "need_two_13f_filings",
                    "filings_found": len(accessions),
                    "authority": "research_only",
                }
            )
        xml_cur = await _fetch_filing_xml(cik, accessions[0])
        xml_prev = await _fetch_filing_xml(cik, accessions[1])
        if not xml_cur or not xml_prev:
            return sanitize_research_payload(
                {
                    "ok": False,
                    "cik": cik,
                    "reason": "xml_parse_unavailable",
                    "authority": "research_only",
                }
            )
        cur_rows = _parse_13f_positions(xml_cur)
        prev_rows = _parse_13f_positions(xml_prev)
        if not cur_rows:
            return sanitize_research_payload(
                {
                    "ok": False,
                    "cik": cik,
                    "reason": "empty_holdings_table",
                    "authority": "research_only",
                }
            )
        diff = _diff_holdings(cur_rows, prev_rows, ticker.upper())
        return sanitize_research_payload(
            {
                "ok": True,
                "cik": cik,
                "ticker": ticker.upper(),
                "accessions": accessions[:2],
                "holdings_rows_latest": len(cur_rows),
                **diff,
                "note": "SEC 13F information table — lagged; values in USD thousands.",
                "authority": "research_only",
            }
        )
    except Exception as exc:
        logger.debug("13F holdings QoQ failed cik=%s: %s", cik, exc)
        return sanitize_research_payload(
            {
                "ok": False,
                "cik": cik,
                "error": type(exc).__name__,
                "authority": "research_only",
            }
        )
