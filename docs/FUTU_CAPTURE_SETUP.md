# Futu Portfolio Capture — Setup

Upload a Futu (富途) portfolio screenshot → auto-detect holdings → AI advisory → Discord notification.

**Advisory only** — never auto-trades. Human approval required for any action.

## Quick start

1. Set env vars (see below).
2. Restart the CC API (`uvicorn src.api.main:app`).
3. Upload via **Portfolio tab → 📸 Futu**, Discord `/portfolio-futu-capture`, or post an image in the configured Discord channel.

## Environment variables

| Variable                       | Required    | Description                                           |
| ------------------------------ | ----------- | ----------------------------------------------------- |
| `OPENAI_API_KEY`               | Recommended | Vision parsing via GPT-4o (or set `OPENCLAW_API_KEY`) |
| `DISCORD_WEBHOOK_URL`          | Optional    | Outbound holdings + AI summary                        |
| `DISCORD_BOT_TOKEN`            | Optional    | Inbound image relay + slash command                   |
| `DISCORD_FUTU_CAPTURE_CHANNEL` | Optional    | Limit auto-parse to one channel (name or ID)          |
| `FUTU_CAPTURE_MAX_BYTES`       | Optional    | Max upload size (default 10MB)                        |

Copy `config/futu_capture.env.example` into your `.env`.

## API

```bash
curl -X POST http://127.0.0.1:8000/api/v7/portfolio/futu-capture \
  -F "file=@/path/to/futu_screenshot.png" \
  -F "notify_discord=true"
```

Optional OCR text fallback (skip vision):

```bash
curl -X POST ... -F "file=@screenshot.png" -F 'ocr_text=NVDA 100 120.5 135.2 +14.7 12.2%'
```

Response includes `holdings`, `advisory` (bilingual summary), `pushed_to_discord`, and `advisory_only: true`.

## Discord

- **Slash command:** `/portfolio-futu-capture` — attach screenshot (requires bot wiring below)
- **Channel drop:** post PNG/JPEG in `DISCORD_FUTU_CAPTURE_CHANNEL` (or any channel if unset)
- **Outbound:** webhook posts parsed table + AI summary with monitor-only footer

### Wire Discord bot (one-time)

After `commands.Bot(...)` is created in `run_interactive_bot`, add:

```python
from src.notifications.futu_capture_discord_handlers import register_futu_capture_handlers

register_futu_capture_handlers(
    bot,
    api_base_url=_API_BASE_URL,
    color_buy=COLOR_BUY,
    color_info=COLOR_INFO,
)
```

Or use the CC API / Portfolio tab upload — no bot changes required for parsing.

## Supported layouts (v1)

- Futu mobile **持仓 / Positions** list (US tickers + HK 5-digit codes)
- Headers: 代码/代碼, 数量/數量, 成本/成本价, 现价/現價, 盈亏/盈虧 (繁中 + English)
- OCR text paste via `ocr_text` form field

**Not yet supported:** options-only screens, multi-account tabs, desktop OpenD export CSV (use `/portfolio-futu` OpenD sync instead).

## Limitations

- Vision quality depends on screenshot clarity and LLM availability.
- Without `OPENAI_API_KEY`, provide `ocr_text` or use text-heavy screenshots only.
- Parsed holdings update the in-memory CC portfolio (`source: futu-capture`); they do not sync to IBKR or execute trades.
