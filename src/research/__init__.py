"""
News Intelligence - AI-powered news analysis and summarization.

Condenses earnings reports, analyst updates, and macroeconomic news
into actionable trading briefs.
"""
_LAZY = {
    "NewsAnalyzer": ".news_analyzer",
    "NewsItem": ".news_analyzer",
    "NewsBrief": ".news_analyzer",
    "EarningsAnalyzer": ".earnings_analyzer",
    "EarningsReport": ".earnings_analyzer",
    "MacroAnalyzer": ".macro_analyzer",
    "MacroEvent": ".macro_analyzer",
}

__all__ = list(_LAZY)


def __getattr__(name):
    if name in _LAZY:
        import importlib

        mod = importlib.import_module(_LAZY[name], __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
