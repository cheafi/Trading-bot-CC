# Telegram Setup — Immediate Opportunity Alerts

Get push notifications on your phone when the playbook scan finds **deploy-qualified** setups or high-tier **monitor** opportunities.

> **Authority:** DEPLOY alerts only fire when a row passes `decision_truth_model.row_passes_trade_bar` (execution-ready + full TRADE bar). WATCH/MONITOR alerts are labeled **NOT deploy permission**.

## 1. Create a bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow prompts.
3. Copy the **HTTP API token** (looks like `123456789:ABC...`).

## 2. Get your chat ID

**Private chat (simplest)**

1. Send any message to your new bot (e.g. `/start`).
2. Open in a browser (replace `TOKEN`):

    ```
    https://api.telegram.org/botTOKEN/getUpdates
    ```

3. Find `"chat":{"id":123456789}` — that number is `TELEGRAM_CHAT_ID`.

**Group chat**

1. Add the bot to the group.
2. Send a message mentioning the bot.
3. Use `getUpdates` as above; group ids are negative (e.g. `-1001234567890`).

## 3. Configure TradingAI Bot

Add to `.env` (or merge `config/telegram.env.example`):

```bash
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Optional — link alerts back to CC when using a tunnel
CC_PUBLIC_BASE_URL=https://your-subdomain.trycloudflare.com
```

Restart the API (`python _cc_instant.py` or `docker compose -f docker-compose.dev.yml up`).

## 4. Verify

```bash
# Status (includes Telegram config, no secrets)
curl -s http://localhost:8000/api/v7/notify/status | python3 -m json.tool

# Test ping
curl -s -X POST "http://localhost:8000/api/v7/notify/telegram/test?message=Hello%20from%20CC"
```

Live opportunity alerts fire automatically after each **live playbook ranked scan** (background refresh, prewarm, or `GET /api/playbook/ranked?refresh=true`). The first scan only seeds state (no flood); subsequent scans alert on new deploy/monitor names, upgrades, or a new #1 ranked ticker.

## Toggles

| Variable                      | Default | Purpose                      |
| ----------------------------- | ------- | ---------------------------- |
| `TELEGRAM_NOTIFY_ENABLED`     | `true`  | Master switch                |
| `TELEGRAM_NOTIFY_DEPLOY`      | `true`  | Deploy-qualified alerts      |
| `TELEGRAM_NOTIFY_MONITOR`     | `true`  | High-tier WATCH / near-miss  |
| `TELEGRAM_ALERT_COOLDOWN_SEC` | `300`   | Dedup window per ticker+tier |
| `TELEGRAM_ALERT_DEDUPE`       | `true`  | Enable deduplication         |

## Security notes

- Never commit real tokens. Use `.env` (gitignored).
- Bot API calls use **HTTPS only** (`api.telegram.org`).
- Logs record success/failure only — tokens are never logged.

See also [CC_PUBLIC_ACCESS.md](CC_PUBLIC_ACCESS.md) for tunnel setup when exposing CC remotely.
