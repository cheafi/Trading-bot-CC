"""
CC - AI Service (Multi-Provider Smart Router)
Routes each AI task to the optimal model via local Docker Model Runner first,
then falls back to external OpenAI-compatible providers when configured.
All calls cached 5 min.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from contextlib import suppress
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

_OPENCLAW_KEY = os.getenv("OPENCLAW_API_KEY", "")
_OPENCLAW_BASE = os.getenv("OPENCLAW_API_BASE", "https://geminiapi.asia/v1")
_NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
_NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
_OPENAI_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

# Azure OpenAI — opt-in via AZURE_OPENAI_ENABLED; supports API key or service principal
_AZURE_ENABLED = os.getenv("AZURE_OPENAI_ENABLED", "").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
_AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
_AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
_AZURE_DEPLOYMENT_NARRATIVE = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_NARRATIVE", _AZURE_DEPLOYMENT
)
_AZURE_DEPLOYMENT_SIGNAL = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_SIGNAL", _AZURE_DEPLOYMENT
)
_AZURE_DEPLOYMENT_QUICK = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_QUICK", _AZURE_DEPLOYMENT
)
_AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2026-01-15-preview")
_AZURE_TENANT = os.getenv("AZURE_TENANT_ID", "")
_AZURE_CLIENT = os.getenv("AZURE_CLIENT_ID", "")
_AZURE_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
_azure_ad_token_cache: Optional[tuple[float, str]] = None

# Docker Model Runner — local LLM (OpenAI-compatible, no key needed)
# Host: http://localhost:12434/engines/llama.cpp/v1
# Container: http://model-runner.docker.internal/engines/llama.cpp/v1
_LOCAL_LLM_URL = os.getenv(
    "LOCAL_LLM_URL",
    (
        "http://model-runner.docker.internal/engines/llama.cpp/v1"
        if os.getenv("RUNNING_IN_DOCKER") == "1"
        else "http://localhost:12434/engines/llama.cpp/v1"
    ),
)
_LOCAL_LLM_ENABLED = os.getenv("LOCAL_LLM_ENABLED", "auto")  # auto|on|off
_LOCAL_MODEL_ADVISOR = os.getenv("LOCAL_MODEL_ADVISOR", "ai/gemma3")
_LOCAL_MODEL_REVIEWER = os.getenv("LOCAL_MODEL_REVIEWER", "ai/qwen3-coder")
_LOCAL_MODEL_EMBED = os.getenv("LOCAL_MODEL_EMBED", "ai/all-minilm-l6-v2-vllm")

_MODEL_NARRATIVE = "gpt-5.4"  # best prose + reasoning
_MODEL_SIGNAL = "gpt-4o"  # fast structured
_MODEL_DOSSIER = "gpt-5.4"  # deep reasoning
_MODEL_QUICK = "gpt-4o-mini"  # cheap & fast
_MODEL_NVIDIA = "nvidia/llama-3.1-nemotron-70b-instruct"
_CACHE_TTL = 300
_TIMEOUT = 90  # local models may be slower on first token

SYSTEM_MARKET_ANALYST = (
    "You are CC (Clarity Console), an elite market intelligence analyst. "
    "You write like a Bloomberg terminal briefing crossed with a hedge-fund morning note. "
    "Rules: Be specific with prices/percentages/R:R. No filler phrases. "
    "Short paragraphs (2-3 sentences). Bold key tickers and levels with **markdown**. "
    "End with actionable sentence. Never hallucinate. Respect regime filter. Max 150 words."
)

SYSTEM_SIGNAL_ANALYST = (
    "You are CC signal reasoning engine. "
    "Rules: Lead with BUY/WATCH/AVOID verdict. Cite entry/target/stop prices. "
    "Explain SETUP, CATALYST, RISK. Use trader shorthand: R:R, ATR, SMA, RSI. "
    "Max 100 words. Never ignore volume."
)

SYSTEM_PM_ADVISOR = (
    "You are CC PM Advisor, a senior fund manager aide. "
    "Respect deterministic signals, risk gates, and regime filters. "
    "Never override hard risk limits. "
    "Always reference conviction tier, regime gate, and R:R when relevant. "
    "Be concise, specific, and decision-oriented."
)

SYSTEM_TRADE_REVIEWER = (
    "You are CC Trade Reviewer. "
    "Review completed trades like a disciplined portfolio manager. "
    "Identify what worked, what failed, and what should change next time. "
    "Never invent facts. If evidence is thin, say so. "
    "Keep answers structured and brief."
)

AI_SETUP_HINT = (
    "Set OPENAI_API_KEY, NVIDIA_API_KEY, OPENCLAW_API_KEY, "
    "AZURE_OPENAI_ENABLED + endpoint/deployment, "
    "or enable LOCAL_LLM_URL (Docker Model Runner)."
)


def _azure_openai_configured() -> bool:
    """True when Azure OpenAI is explicitly enabled with HTTPS endpoint and auth."""
    if not _AZURE_ENABLED or not _AZURE_ENDPOINT or not _AZURE_DEPLOYMENT:
        return False
    if not _AZURE_ENDPOINT.startswith("https://"):
        logger.warning("[AI] AZURE_OPENAI_ENDPOINT must use HTTPS")
        return False
    return bool(_AZURE_KEY) or all((_AZURE_TENANT, _AZURE_CLIENT, _AZURE_SECRET))


def _resolve_azure_deployment(preferred_model: Optional[str]) -> str:
    if preferred_model in (_MODEL_NARRATIVE, _MODEL_DOSSIER):
        return _AZURE_DEPLOYMENT_NARRATIVE or _AZURE_DEPLOYMENT
    if preferred_model == _MODEL_SIGNAL:
        return _AZURE_DEPLOYMENT_SIGNAL or _AZURE_DEPLOYMENT
    return _AZURE_DEPLOYMENT_QUICK or _AZURE_DEPLOYMENT


def _get_azure_bearer_token() -> Optional[str]:
    """Fetch Azure AD token for service-principal auth (cached until expiry)."""
    global _azure_ad_token_cache
    if _AZURE_KEY:
        return None
    now = time.time()
    if _azure_ad_token_cache and _azure_ad_token_cache[0] > now + 60:
        return _azure_ad_token_cache[1]
    try:
        from azure.identity import ClientSecretCredential

        credential = ClientSecretCredential(
            tenant_id=_AZURE_TENANT,
            client_id=_AZURE_CLIENT,
            client_secret=_AZURE_SECRET,
        )
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        _azure_ad_token_cache = (token.expires_on, token.token)
        return token.token
    except Exception as exc:
        logger.warning("[AI] Azure AD token fetch failed: %s", exc)
        return None


def build_stub_narrative(
    regime: Dict[str, Any],
    top_signals: List[Dict[str, Any]],
    pulse: Dict[str, Any],
    funnel: Dict[str, Any],
    board_narrative: str = "",
) -> str:
    """Deterministic narrative when no LLM is configured or all providers fail."""
    trend = regime.get("trend") or regime.get("label") or "unknown"
    tradeability = regime.get("tradeability") or (
        "open" if regime.get("should_trade", True) else "wait"
    )
    vix = regime.get("vix")
    breadth = regime.get("breadth")
    regime_bits = [f"Regime **{trend}**", f"tradeability **{tradeability}**"]
    if vix is not None:
        regime_bits.append(f"VIX **{float(vix):.0f}**")
    if breadth is not None:
        regime_bits.append(f"breadth **{float(breadth):.0f}%**")

    funnel_bits = []
    if funnel:
        universe = funnel.get("universe")
        actionable = funnel.get("actionable_above_7")
        high_conv = funnel.get("high_conviction_above_8")
        if universe is not None:
            funnel_bits.append(f"{universe} scanned")
        if actionable is not None:
            funnel_bits.append(f"{actionable} actionable (score ≥7)")
        if high_conv is not None:
            funnel_bits.append(f"{high_conv} high-conviction (≥8)")

    sig_lines = []
    for i, sig in enumerate(top_signals[:5], 1):
        ticker = sig.get("ticker") or "?"
        score = sig.get("score", 0)
        strategy = sig.get("strategy") or "setup"
        rr = sig.get("risk_reward", 0)
        sig_lines.append(
            f"{i}. **{ticker}** — score {float(score):.1f}, {strategy}, R:R {float(rr):.1f}"
        )

    paragraphs = [
        "Rule-based briefing (narrative only — does not affect ranking, sizing, or deploy gates).",
        " · ".join(regime_bits) + ".",
    ]
    if funnel_bits:
        paragraphs.append("Funnel: " + ", ".join(funnel_bits) + ".")
    if sig_lines:
        paragraphs.append("Top board:\n" + "\n".join(sig_lines))
    elif board_narrative:
        paragraphs.append(board_narrative.strip()[:600])
    else:
        paragraphs.append(
            "No ranked setups on the board yet — observe until the funnel clears."
        )

    action = (
        "Bias: selective adds only where the board and regime align."
        if str(tradeability).upper() not in ("NO_TRADE", "WAIT", "REDUCE")
        else "Bias: restraint — prioritize capital preservation and monitor triggers."
    )
    paragraphs.append(action)
    return "\n\n".join(paragraphs)


class _AICache:
    def __init__(self):
        self._store: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[str]:
        e = self._store.get(key)
        return e[1] if e and (time.monotonic() - e[0]) < _CACHE_TTL else None

    def set(self, key: str, value: str):
        self._store[key] = (time.monotonic(), value)

    def stats(self) -> Dict[str, int]:
        now = time.monotonic()
        total = len(self._store)
        fresh = len([1 for t, _ in self._store.values() if now - t < _CACHE_TTL])
        return {"total": total, "fresh": fresh}


class AIService:
    """Multi-provider AI service with smart model routing."""

    def __init__(self):
        self._cache = _AICache()
        self._session: Optional[aiohttp.ClientSession] = None
        self._call_count = 0
        self._error_count = 0
        self._provider_used = "none"
        self._last_model = ""
        self._local_llm_ok: bool = False  # set by probe_local_llm()
        self._disabled_providers: set[str] = set()

    @property
    def is_configured(self) -> bool:
        return bool(
            self._local_llm_ok
            or (_OPENCLAW_KEY and "openclaw" not in self._disabled_providers)
            or (_NVIDIA_KEY and "nvidia" not in self._disabled_providers)
            or (
                _azure_openai_configured()
                and "azure_openai" not in self._disabled_providers
            )
            or (_OPENAI_KEY and "openai" not in self._disabled_providers)
        )

    @property
    def local_llm_available(self) -> bool:
        return self._local_llm_ok

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured,
            "providers": {
                "local_llm": self._local_llm_ok,
                "local_llm_url": _LOCAL_LLM_URL,
                "local_model_advisor": _LOCAL_MODEL_ADVISOR,
                "local_model_reviewer": _LOCAL_MODEL_REVIEWER,
                "local_model_embed": _LOCAL_MODEL_EMBED,
                "openclaw": bool(_OPENCLAW_KEY)
                and "openclaw" not in self._disabled_providers,
                "nvidia": bool(_NVIDIA_KEY)
                and "nvidia" not in self._disabled_providers,
                "openai": bool(_OPENAI_KEY)
                and "openai" not in self._disabled_providers,
                "azure_openai": _azure_openai_configured()
                and "azure_openai" not in self._disabled_providers,
                "azure_openai_endpoint": _AZURE_ENDPOINT or None,
                "azure_openai_deployment": _AZURE_DEPLOYMENT or None,
            },
            "disabled_providers": sorted(self._disabled_providers),
            "last_provider": self._provider_used,
            "last_model": self._last_model,
            "calls": self._call_count,
            "errors": self._error_count,
            "cache": self._cache.stats(),
        }

    def _disable_provider(self, provider_name: str, reason: str) -> None:
        if provider_name == "local_llm":
            self._local_llm_ok = False
        else:
            self._disabled_providers.add(provider_name)
        logger.warning("[AI] disabling provider %s: %s", provider_name, reason)

    async def probe_local_llm(self) -> bool:
        """Check if Docker Model Runner is reachable and has models loaded."""
        if _LOCAL_LLM_ENABLED == "off":
            self._local_llm_ok = False
            return False
        try:
            session = await self._get_session()
            async with session.get(
                f"{_LOCAL_LLM_URL}/models",
                timeout=aiohttp.ClientTimeout(total=5, connect=2, sock_connect=2),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    model_ids = [m.get("id", "") for m in data.get("data", [])]
                    self._local_llm_ok = bool(model_ids)
                    if self._local_llm_ok:
                        logger.info(
                            "[AI] Docker Model Runner online — models: %s",
                            ", ".join(model_ids),
                        )
                    return self._local_llm_ok
        except Exception as exc:
            logger.debug("[AI] Local LLM probe failed: %s", exc)
        self._local_llm_ok = False
        return False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=_TIMEOUT)
            )
        return self._session

    async def _call_provider(
        self,
        base_url,
        api_key,
        model,
        messages,
        max_tokens,
        temperature,
        provider_name,
        response_format=None,
    ):
        """Call a single OpenAI-compatible provider."""
        session = await self._get_session()
        try:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            }
            if response_format is not None:
                payload["response_format"] = response_format
            async with session.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers={
                    **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"]
                    self._call_count += 1
                    self._provider_used = provider_name
                    self._last_model = model
                    logger.info(
                        "[AI] %s/%s -> %d chars", provider_name, model, len(text)
                    )
                    return text
                body = await resp.text()
                if resp.status in (401, 403):
                    self._disable_provider(provider_name, f"auth {resp.status}")
                elif provider_name == "local_llm" and resp.status >= 400:
                    self._disable_provider(provider_name, f"status {resp.status}")
                logger.warning("[AI] %s %s: %s", provider_name, resp.status, body[:200])
        except Exception as exc:
            if provider_name == "local_llm":
                self._disable_provider(provider_name, str(exc))
            logger.warning("[AI] %s error: %s", provider_name, exc)
            self._error_count += 1
        return None

    async def _call_azure_provider(
        self,
        deployment: str,
        messages,
        max_tokens,
        temperature,
        response_format=None,
    ):
        """Call Azure OpenAI chat completions (HTTPS only, deployment-based routing)."""
        if not _azure_openai_configured() or "azure_openai" in self._disabled_providers:
            return None
        session = await self._get_session()
        url = (
            f"{_AZURE_ENDPOINT}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={_AZURE_API_VERSION}"
        )
        headers = {"Content-Type": "application/json"}
        if _AZURE_KEY:
            headers["api-key"] = _AZURE_KEY
        else:
            token = _get_azure_bearer_token()
            if not token:
                self._disable_provider("azure_openai", "Azure AD token unavailable")
                return None
            headers["Authorization"] = f"Bearer {token}"

        payload: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"]
                    self._call_count += 1
                    self._provider_used = "azure_openai"
                    self._last_model = deployment
                    logger.info(
                        "[AI] azure_openai/%s -> %d chars", deployment, len(text)
                    )
                    return text
                body = await resp.text()
                if resp.status in (401, 403):
                    self._disable_provider("azure_openai", f"auth {resp.status}")
                logger.warning(
                    "[AI] azure_openai %s: %s", resp.status, body[:200]
                )
        except Exception as exc:
            logger.warning("[AI] azure_openai error: %s", exc)
            self._error_count += 1
        return None

    def _resolve_local_model(self, preferred_model: str) -> str:
        if preferred_model in (_MODEL_NARRATIVE, _MODEL_DOSSIER, _MODEL_QUICK):
            return _LOCAL_MODEL_ADVISOR
        if preferred_model == _MODEL_SIGNAL:
            return _LOCAL_MODEL_REVIEWER
        return _LOCAL_MODEL_ADVISOR

    async def _call_llm(
        self,
        system,
        user_prompt,
        max_tokens=800,
        temperature=0.3,
        preferred_model=None,
        response_format=None,
    ):
        """Route to best available provider with fallback chain."""
        if preferred_model is None:
            preferred_model = _MODEL_QUICK
        cache_key = hashlib.md5(
            f"{preferred_model}:{response_format}:{system[:40]}:{user_prompt[:200]}".encode()
        ).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        if not self.is_configured:
            return None

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]
        # Build provider chain: Local Docker LLM -> OpenClaw -> NVIDIA -> OpenAI
        chain = []
        if self._local_llm_ok and _LOCAL_LLM_ENABLED != "off":
            local_model = self._resolve_local_model(preferred_model)
            chain.append((_LOCAL_LLM_URL, "", local_model, "local_llm"))
        if _OPENCLAW_KEY and "openclaw" not in self._disabled_providers:
            chain.append((_OPENCLAW_BASE, _OPENCLAW_KEY, preferred_model, "openclaw"))
        if _NVIDIA_KEY and "nvidia" not in self._disabled_providers:
            chain.append((_NVIDIA_BASE, _NVIDIA_KEY, _MODEL_NVIDIA, "nvidia"))
        if _azure_openai_configured() and "azure_openai" not in self._disabled_providers:
            azure_deployment = _resolve_azure_deployment(preferred_model)
            azure_text = await self._call_azure_provider(
                azure_deployment,
                messages,
                max_tokens,
                temperature,
                response_format=response_format,
            )
            if azure_text:
                self._cache.set(cache_key, azure_text)
                return azure_text
        if _OPENAI_KEY and "openai" not in self._disabled_providers:
            chain.append((_OPENAI_BASE, _OPENAI_KEY, _MODEL_QUICK, "openai"))

        for base, key, model, name in chain:
            text = await self._call_provider(
                base,
                key,
                model,
                messages,
                max_tokens,
                temperature,
                name,
                response_format=response_format,
            )
            if text:
                self._cache.set(cache_key, text)
                return text
        self._error_count += 1
        return None

    @staticmethod
    def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        stripped = text.strip()
        with suppress(Exception):
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    async def generate_json(
        self,
        system: str,
        user_prompt: str,
        preferred_model: Optional[str] = None,
        max_tokens: int = 700,
    ) -> Optional[Dict[str, Any]]:
        text = await self._call_llm(
            system,
            user_prompt + "\nReturn valid JSON only.",
            max_tokens=max_tokens,
            temperature=0.2,
            preferred_model=preferred_model,
            response_format={"type": "json_object"},
        )
        parsed = self._extract_json_block(text or "")
        if parsed is not None:
            return parsed
        text = await self._call_llm(
            system,
            user_prompt + "\nReturn valid JSON only.",
            max_tokens=max_tokens,
            temperature=0.2,
            preferred_model=preferred_model,
        )
        return self._extract_json_block(text or "")

    async def analyze_image_json(
        self,
        system: str,
        user_prompt: str,
        image_url: str,
        preferred_model: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> Optional[Dict[str, Any]]:
        """Vision LLM — extract structured JSON from an image (OpenAI-compatible)."""
        if not self.is_configured:
            return None
        model = preferred_model or _MODEL_SIGNAL
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ]
        if _azure_openai_configured() and "azure_openai" not in self._disabled_providers:
            azure_deployment = _resolve_azure_deployment(model)
            text = await self._call_azure_provider(
                azure_deployment,
                messages,
                max_tokens,
                0.1,
                response_format={"type": "json_object"},
            )
            parsed = self._extract_json_block(text or "")
            if parsed is not None:
                return parsed

        chain = []
        if _OPENCLAW_KEY and "openclaw" not in self._disabled_providers:
            chain.append((_OPENCLAW_BASE, _OPENCLAW_KEY, model, "openclaw"))
        if _OPENAI_KEY and "openai" not in self._disabled_providers:
            chain.append((_OPENAI_BASE, _OPENAI_KEY, model, "openai"))
        for base, key, m, name in chain:
            text = await self._call_provider(
                base,
                key,
                m,
                messages,
                max_tokens,
                0.1,
                name,
                response_format={"type": "json_object"},
            )
            parsed = self._extract_json_block(text or "")
            if parsed is not None:
                return parsed
        return None

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if not (self._local_llm_ok and _LOCAL_LLM_ENABLED != "off"):
            return []
        session = await self._get_session()
        try:
            async with session.post(
                f"{_LOCAL_LLM_URL}/embeddings",
                json={"model": _LOCAL_MODEL_EMBED, "input": texts},
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    self._disable_provider(
                        "local_llm", f"embeddings status {resp.status}"
                    )
                    logger.warning("[AI] embeddings %s: %s", resp.status, body[:200])
                    return []
                data = await resp.json()
                rows = data.get("data", [])
                vectors = [row.get("embedding", []) for row in rows]
                self._provider_used = "local_llm"
                self._last_model = _LOCAL_MODEL_EMBED
                return [v for v in vectors if isinstance(v, list)]
        except Exception as exc:
            self._disable_provider("local_llm", f"embeddings error: {exc}")
            logger.warning("[AI] embeddings error: %s", exc)
            return []

    # ── High-level API ───────────────────────────────────────────

    async def generate_narrative(self, regime, top_signals, pulse, funnel):
        """Morning briefing -> Claude (best prose)."""
        sigs = "\n".join(
            f"{i}. {s.get('ticker', '?')} Score {s.get('score', 0):.1f} "
            f"{s.get('strategy', '?')} R:R {s.get('risk_reward', 0):.1f} "
            f"Entry ${s.get('entry_price', 0):.2f}"
            for i, s in enumerate(top_signals[:5], 1)
        )
        prompt = (
            f"Morning briefing.\n"
            f"REGIME: {regime.get('trend', '?')} {regime.get('volatility', '?')} vol "
            f"VIX {regime.get('vix', 18)} Breadth {regime.get('breadth', 50)}% "
            f"Trade: {regime.get('should_trade', True)}\n"
            f"FUNNEL: {funnel.get('universe', 0)} scanned "
            f"{funnel.get('actionable_above_7', 0)} actionable "
            f"{funnel.get('high_conviction_above_8', 0)} high-conviction\n"
            f"PULSE: {json.dumps(pulse, default=str)[:400]}\n"
            f"TOP SIGNALS:\n{sigs}\n"
            f"Write 2-3 paragraphs: regime outlook, opportunities, action guidance."
        )
        return await self._call_llm(
            SYSTEM_MARKET_ANALYST,
            prompt,
            max_tokens=500,
            preferred_model=_MODEL_NARRATIVE,
        )

    async def analyze_signal(self, signal):
        """Signal card -> GPT-4o (fast structured)."""
        prompt = (
            f"Trade setup: {signal.get('ticker', '?')} {signal.get('strategy', '?')} "
            f"Score {signal.get('score', 0):.1f}/10 R:R {signal.get('risk_reward', 0):.1f}\n"
            f"Entry ${signal.get('entry_price', 0):.2f} "
            f"Target ${signal.get('target_price', 0):.2f} "
            f"Stop ${signal.get('stop_price', 0):.2f}\n"
            f"RSI {signal.get('rsi', 50):.0f} Vol {signal.get('vol_ratio', 1.0):.1f}x "
            f"ATR {signal.get('atr_pct', 1.0):.1f}% {signal.get('regime', '?')}\n"
            f"Give: VERDICT, SETUP (2 sent), CATALYST (1 sent), KEY RISK (1 sent)"
        )
        text = await self._call_llm(
            SYSTEM_SIGNAL_ANALYST,
            prompt,
            max_tokens=250,
            preferred_model=_MODEL_SIGNAL,
        )
        if not text:
            return None
        return {
            "ai_analysis": text,
            "ai_provider": self._provider_used,
            "ai_model": self._last_model,
        }

    async def analyze_dossier(self, ticker, technicals, trade_plan, regime):
        """Deep dossier -> Claude (deep reasoning)."""
        ez = trade_plan.get("entry_zone", [0, 0])
        prompt = (
            f"Deep analysis: {ticker}\n"
            f"Price ${technicals.get('price', 0):.2f} "
            f"({technicals.get('change_pct', 0):+.2f}%)\n"
            f"RSI {technicals.get('rsi', 50):.0f} "
            f"MACD {technicals.get('macd_signal', '?')}\n"
            f"SMA20 {'up' if technicals.get('above_sma20') else 'dn'} "
            f"SMA50 {'up' if technicals.get('above_sma50') else 'dn'} "
            f"SMA200 {'up' if technicals.get('above_sma200') else 'dn'}\n"
            f"Volume {technicals.get('vol_ratio', 1.0):.1f}x "
            f"ATR ${technicals.get('atr', 0):.2f}\n"
            f"52W: ${technicals.get('low_52w', 0):.2f}"
            f"-${technicals.get('high_52w', 0):.2f}\n"
            f"Support ${technicals.get('support', 0):.2f} "
            f"Resist ${technicals.get('resistance', 0):.2f}\n"
            f"Plan: Entry ${ez[0]:.2f}-${ez[1]:.2f} "
            f"T1 ${trade_plan.get('target_1r', 0):.2f} "
            f"Stop ${trade_plan.get('stop', 0):.2f}\n"
            f"Regime: {regime.get('label', '?')} "
            f"trade={regime.get('should_trade', True)}\n"
            f"3 paragraphs: STRUCTURE, SETUP, PLAN with conviction level."
        )
        return await self._call_llm(
            SYSTEM_MARKET_ANALYST,
            prompt,
            max_tokens=500,
            preferred_model=_MODEL_DOSSIER,
        )

    async def generate_brief(self, portfolio, regime):
        """Portfolio brief -> GPT-4o-mini (fast)."""
        holdings = (
            "\n".join(
                f"- {h.get('ticker', '?')}: {h.get('qty', 0)} sh "
                f"@ ${h.get('avg_cost', 0):.2f}, "
                f"P&L {h.get('pnl_pct', 0):.1f}%"
                for h in portfolio[:10]
            )
            or "No positions"
        )
        prompt = (
            f"Portfolio brief:\n{holdings}\n"
            f"Regime: {regime.get('label', '?')} {regime.get('trend', '?')} "
            f"VIX {regime.get('vix', 18):.0f}\n"
            f"2 paragraphs: EXPOSURE (risk, sectors), ACTION (trim/hold/add for this regime)"
        )
        return await self._call_llm(
            SYSTEM_MARKET_ANALYST,
            prompt,
            max_tokens=350,
            preferred_model=_MODEL_QUICK,
        )

    async def generate_pm_memo(self, context: str) -> Optional[str]:
        return await self._call_llm(
            SYSTEM_PM_ADVISOR,
            context,
            max_tokens=350,
            preferred_model=_MODEL_NARRATIVE,
        )

    async def review_trade(self, context: str) -> Optional[Dict[str, Any]]:
        return await self.generate_json(
            SYSTEM_TRADE_REVIEWER,
            context,
            preferred_model=_MODEL_SIGNAL,
            max_tokens=500,
        )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


_instance: Optional[AIService] = None


def get_ai_service() -> AIService:
    global _instance
    if _instance is None:
        _instance = AIService()
    return _instance
