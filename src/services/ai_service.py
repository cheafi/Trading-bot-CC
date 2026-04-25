"""
CC - AI Service (Multi-Provider Smart Router)
Routes each AI task to the optimal model via OpenClaw gateway.
Provider priority: OpenClaw -> NVIDIA NIM -> OpenAI direct
All calls cached 5 min.
"""
from __future__ import annotations
import hashlib, json, logging, os, time
from typing import Any, Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)

_OPENCLAW_KEY = os.getenv("OPENCLAW_API_KEY", "")
_OPENCLAW_BASE = os.getenv("OPENCLAW_API_BASE", "https://geminiapi.asia/v1")
_NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
_NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
_OPENAI_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

_MODEL_NARRATIVE = "gpt-5.4"              # best prose + reasoning
_MODEL_SIGNAL = "gpt-4o"                 # fast structured
_MODEL_DOSSIER = "gpt-5.4"               # deep reasoning
_MODEL_QUICK = "gpt-4o-mini"             # cheap & fast
_MODEL_NVIDIA = "nvidia/llama-3.1-nemotron-70b-instruct"
_CACHE_TTL = 300
_TIMEOUT = 45

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


class _AICache:
    def __init__(self):
        self._store: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[str]:
        e = self._store.get(key)
        if e and (time.monotonic() - e[0]) < _CACHE_TTL:
            return e[1]
        return None

    def set(self, key: str, value: str):
        self._store[key] = (time.monotonic(), value)

    def stats(self) -> Dict[str, int]:
        now = time.monotonic()
        total = len(self._store)
        fresh = sum(1 for t, _ in self._store.values() if now - t < _CACHE_TTL)
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

    @property
    def is_configured(self) -> bool:
        return bool(_OPENCLAW_KEY or _NVIDIA_KEY or _OPENAI_KEY)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured,
            "providers": {
                "openclaw": bool(_OPENCLAW_KEY),
                "nvidia": bool(_NVIDIA_KEY),
                "openai": bool(_OPENAI_KEY),
            },
            "last_provider": self._provider_used,
            "last_model": self._last_model,
            "calls": self._call_count,
            "errors": self._error_count,
            "cache": self._cache.stats(),
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=_TIMEOUT)
            )
        return self._session

    async def _call_provider(self, base_url, api_key, model, messages, max_tokens, temperature, provider_name):
        """Call a single OpenAI-compatible provider."""
        session = await self._get_session()
        try:
            async with session.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"]
                    self._call_count += 1
                    self._provider_used = provider_name
                    self._last_model = model
                    logger.info("[AI] %s/%s -> %d chars", provider_name, model, len(text))
                    return text
                body = await resp.text()
                logger.warning("[AI] %s %s: %s", provider_name, resp.status, body[:200])
        except Exception as exc:
            logger.warning("[AI] %s error: %s", provider_name, exc)
            self._error_count += 1
        return None

    async def _call_llm(self, system, user_prompt, max_tokens=800, temperature=0.3, preferred_model=None):
        """Route to best available provider with fallback chain."""
        if preferred_model is None:
            preferred_model = _MODEL_QUICK
        cache_key = hashlib.md5(
            f"{preferred_model}:{system[:40]}:{user_prompt[:200]}".encode()
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
        # Build provider chain: OpenClaw (multi-model) -> NVIDIA -> OpenAI
        chain = []
        if _OPENCLAW_KEY:
            chain.append((_OPENCLAW_BASE, _OPENCLAW_KEY, preferred_model, "openclaw"))
        if _NVIDIA_KEY:
            chain.append((_NVIDIA_BASE, _NVIDIA_KEY, _MODEL_NVIDIA, "nvidia"))
        if _OPENAI_KEY:
            chain.append((_OPENAI_BASE, _OPENAI_KEY, _MODEL_QUICK, "openai"))

        for base, key, model, name in chain:
            text = await self._call_provider(base, key, model, messages, max_tokens, temperature, name)
            if text:
                self._cache.set(cache_key, text)
                return text
        self._error_count += 1
        return None

    # ── High-level API ───────────────────────────────────────────

    async def generate_narrative(self, regime, top_signals, pulse, funnel):
        """Morning briefing -> Claude (best prose)."""
        sigs = "\n".join(
            f"{i}. {s.get('ticker','?')} Score {s.get('score',0):.1f} "
            f"{s.get('strategy','?')} R:R {s.get('risk_reward',0):.1f} "
            f"Entry ${s.get('entry_price',0):.2f}"
            for i, s in enumerate(top_signals[:5], 1)
        )
        prompt = (
            f"Morning briefing.\n"
            f"REGIME: {regime.get('trend','?')} {regime.get('volatility','?')} vol "
            f"VIX {regime.get('vix',18)} Breadth {regime.get('breadth',50)}% "
            f"Trade: {regime.get('should_trade',True)}\n"
            f"FUNNEL: {funnel.get('universe',0)} scanned "
            f"{funnel.get('actionable_above_7',0)} actionable "
            f"{funnel.get('high_conviction_above_8',0)} high-conviction\n"
            f"PULSE: {json.dumps(pulse, default=str)[:400]}\n"
            f"TOP SIGNALS:\n{sigs}\n"
            f"Write 2-3 paragraphs: regime outlook, opportunities, action guidance."
        )
        return await self._call_llm(
            SYSTEM_MARKET_ANALYST, prompt,
            max_tokens=500, preferred_model=_MODEL_NARRATIVE,
        )

    async def analyze_signal(self, signal):
        """Signal card -> GPT-4o (fast structured)."""
        prompt = (
            f"Trade setup: {signal.get('ticker','?')} {signal.get('strategy','?')} "
            f"Score {signal.get('score',0):.1f}/10 R:R {signal.get('risk_reward',0):.1f}\n"
            f"Entry ${signal.get('entry_price',0):.2f} "
            f"Target ${signal.get('target_price',0):.2f} "
            f"Stop ${signal.get('stop_price',0):.2f}\n"
            f"RSI {signal.get('rsi',50):.0f} Vol {signal.get('vol_ratio',1.0):.1f}x "
            f"ATR {signal.get('atr_pct',1.0):.1f}% {signal.get('regime','?')}\n"
            f"Give: VERDICT, SETUP (2 sent), CATALYST (1 sent), KEY RISK (1 sent)"
        )
        text = await self._call_llm(
            SYSTEM_SIGNAL_ANALYST, prompt,
            max_tokens=250, preferred_model=_MODEL_SIGNAL,
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
            f"Price ${technicals.get('price',0):.2f} "
            f"({technicals.get('change_pct',0):+.2f}%)\n"
            f"RSI {technicals.get('rsi',50):.0f} "
            f"MACD {technicals.get('macd_signal','?')}\n"
            f"SMA20 {'up' if technicals.get('above_sma20') else 'dn'} "
            f"SMA50 {'up' if technicals.get('above_sma50') else 'dn'} "
            f"SMA200 {'up' if technicals.get('above_sma200') else 'dn'}\n"
            f"Volume {technicals.get('vol_ratio',1.0):.1f}x "
            f"ATR ${technicals.get('atr',0):.2f}\n"
            f"52W: ${technicals.get('low_52w',0):.2f}"
            f"-${technicals.get('high_52w',0):.2f}\n"
            f"Support ${technicals.get('support',0):.2f} "
            f"Resist ${technicals.get('resistance',0):.2f}\n"
            f"Plan: Entry ${ez[0]:.2f}-${ez[1]:.2f} "
            f"T1 ${trade_plan.get('target_1r',0):.2f} "
            f"Stop ${trade_plan.get('stop',0):.2f}\n"
            f"Regime: {regime.get('label','?')} "
            f"trade={regime.get('should_trade',True)}\n"
            f"3 paragraphs: STRUCTURE, SETUP, PLAN with conviction level."
        )
        return await self._call_llm(
            SYSTEM_MARKET_ANALYST, prompt,
            max_tokens=500, preferred_model=_MODEL_DOSSIER,
        )

    async def generate_brief(self, portfolio, regime):
        """Portfolio brief -> GPT-4o-mini (fast)."""
        holdings = "\n".join(
            f"- {h.get('ticker','?')}: {h.get('qty',0)} sh "
            f"@ ${h.get('avg_cost',0):.2f}, "
            f"P&L {h.get('pnl_pct',0):.1f}%"
            for h in portfolio[:10]
        ) or "No positions"
        prompt = (
            f"Portfolio brief:\n{holdings}\n"
            f"Regime: {regime.get('label','?')} {regime.get('trend','?')} "
            f"VIX {regime.get('vix',18):.0f}\n"
            f"2 paragraphs: EXPOSURE (risk, sectors), ACTION (trim/hold/add for this regime)"
        )
        return await self._call_llm(
            SYSTEM_MARKET_ANALYST, prompt,
            max_tokens=350, preferred_model=_MODEL_QUICK,
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
