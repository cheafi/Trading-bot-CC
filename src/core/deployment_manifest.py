"""Human-only deployment manifest — learning loops may never write this file."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.core.state_paths import atomic_write_text, deployment_manifest_path

logger = logging.getLogger(__name__)

_RESEARCH_ONLY_CALLERS = frozenset(
    {
        "autonomous_learning_loop",
        "self_learning",
        "strategy_fitness",
        "gpt_validator",
    }
)


def _empty_manifest() -> Dict[str, Any]:
    return {
        "deploy_open": False,
        "updated_by": "system",
        "updated_at": None,
        "authority": "human_only",
        "may_authorize_deploy": False,
        "candidates": [],
    }


def load_deployment_manifest(
    *,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    target = path or deployment_manifest_path()
    if not target.is_file():
        return _empty_manifest()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty_manifest()
        data.setdefault("deploy_open", False)
        data.setdefault("authority", "human_only")
        data.setdefault("may_authorize_deploy", False)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("deployment manifest load failed: %s", exc)
        return _empty_manifest()


def write_deployment_manifest(
    payload: Dict[str, Any],
    *,
    updated_by: str,
    caller: str = "ops",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Persist manifest — blocks research-only callers (IDOS mechanical separation)."""
    if caller in _RESEARCH_ONLY_CALLERS:
        raise PermissionError(
            f"{caller} may not write deployment manifest (research_only)"
        )

    target = path or deployment_manifest_path()
    body = dict(payload)
    body["updated_by"] = updated_by
    body["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body["authority"] = "human_only"
    body.setdefault("deploy_open", False)
    body.setdefault("may_authorize_deploy", bool(body.get("deploy_open")))
    atomic_write_text(target, json.dumps(body, indent=2))
    return body


def audit_deploy_open_provenance(
    *,
    deploy_open: bool,
    source: str,
    llm_vote: bool = False,
) -> Dict[str, Any]:
    """Provenance envelope for deploy_open — LLM votes never grant broker eligibility."""
    return {
        "deploy_open": bool(deploy_open),
        "source": source,
        "authority": "human_only" if deploy_open else "research_only",
        "may_authorize_deploy": False,
        "broker_eligible": bool(deploy_open) and not llm_vote,
        "llm_vote_affects_broker": False,
    }
