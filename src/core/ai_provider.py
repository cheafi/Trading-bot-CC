"""AI provider resolution — research_only authority boundary.

Centralises env-based LLM / Azure Search configuration so entry layers
(engines, knowledge retrieval) do not duplicate provider wiring.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any

AUTHORITY_RESEARCH_ONLY = "research_only"


class LLMProvider(str, Enum):
    STUB = "stub"
    LOCAL_LLM = "local_llm"
    OPENCLAW = "openclaw"
    NVIDIA = "nvidia"
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def openai_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def azure_openai_configured() -> bool:
    """True when Azure OpenAI is explicitly enabled with HTTPS endpoint and auth."""
    if not _env_bool("AZURE_OPENAI_ENABLED"):
        return False
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    if not endpoint.startswith("https://") or not deployment:
        return False
    if os.getenv("AZURE_OPENAI_API_KEY", "").strip():
        return True
    return all(
        os.getenv(k, "").strip()
        for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
    )


def local_llm_configured() -> bool:
    if os.getenv("LOCAL_LLM_ENABLED", "auto").lower() == "off":
        return False
    return bool(os.getenv("LOCAL_LLM_URL", "").strip())


def azure_search_configured() -> bool:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    index = os.getenv("AZURE_SEARCH_INDEX", "").strip()
    key = (
        os.getenv("AZURE_SEARCH_KEY", "").strip()
        or os.getenv("AZURE_SEARCH_API_KEY", "").strip()
    )
    return bool(endpoint.startswith("https://") and index and key)


def resolve_llm_provider() -> LLMProvider:
    """Pick the highest-priority configured provider (stub when none)."""
    if local_llm_configured():
        return LLMProvider.LOCAL_LLM
    if os.getenv("OPENCLAW_API_KEY", "").strip():
        return LLMProvider.OPENCLAW
    if os.getenv("NVIDIA_API_KEY", "").strip():
        return LLMProvider.NVIDIA
    if azure_openai_configured():
        return LLMProvider.AZURE_OPENAI
    if openai_configured():
        return LLMProvider.OPENAI
    return LLMProvider.STUB


def provider_status() -> dict[str, Any]:
    provider = resolve_llm_provider()
    return {
        "provider": provider.value,
        "configured": provider != LLMProvider.STUB,
        "openai": openai_configured(),
        "azure_openai": azure_openai_configured(),
        "local_llm": local_llm_configured(),
        "azure_search": azure_search_configured(),
        "authority": AUTHORITY_RESEARCH_ONLY,
    }
