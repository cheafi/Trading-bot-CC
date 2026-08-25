"""Format evidence fields for UI/API — never emit ``[object Object]``."""

from __future__ import annotations

from typing import List, Union

EvidenceValue = Union[str, int, float, bool, dict, list, None]


def format_evidence(
    value: EvidenceValue, *, default: str = "Evidence unavailable"
) -> str:
    """Render evidence_quality / evidence_strength for display."""
    if value is None or value == "":
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else default
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            text = format_evidence(item, default="")
            if text:
                parts.append(text)
        return " · ".join(parts) if parts else default
    if isinstance(value, dict):
        label = value.get("label") or value.get("tier") or value.get("badge")
        if label is not None and str(label).strip():
            return str(label).strip()
        bits: List[str] = []
        if value.get("validated_score") is not None:
            bits.append(f"Evidence score {value['validated_score']}")
        data_conf = value.get("data_conf")
        if data_conf is not None:
            conf = float(data_conf)
            pct = conf * 100 if conf <= 1 else conf
            bits.append(f"data quality {pct:.0f}%")
        if value.get("calibration_available"):
            bits.append("calibrated")
        return " · ".join(bits) if bits else default
    return default


def playbook_evidence_line(
    value: EvidenceValue, *, default: str = "Evidence unavailable"
) -> str:
    """Playbook card evidence — score + data quality wording."""
    if value is None or value == "":
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else default
    if isinstance(value, dict):
        bits: List[str] = []
        if value.get("validated_score") is not None:
            bits.append(f"Evidence score {value['validated_score']}")
        data_conf = value.get("data_conf")
        if data_conf is not None:
            conf = float(data_conf)
            pct = conf * 100 if conf <= 1 else conf
            bits.append(f"data quality {pct:.0f}%")
        if value.get("calibration_available"):
            bits.append("calibrated")
        if bits:
            return " · ".join(bits)
        return format_evidence(value, default=default)
    return format_evidence(value, default=default)
