# Telegram Setup — CC Live Intelligence

Professional live signal delivery for **CC Operator Decision OS**: deploy-qualified alerts, high-tier monitor signals, and actionable deep links — bilingual (English · 繁中).

> **Authority:** DEPLOY alerts only fire when a row passes `decision_truth_model.row_passes_trade_bar` (execution-ready + full TRADE bar). WATCH/MONITOR alerts are labeled **NOT deploy permission**.

## Bot profile (@TradingAI_AlertsCC_bot)

Configure in [@BotFather](https://t.me/BotFather) or via API (`POST /api/v7/notify/telegram/configure-profile`).

### Short description (`/setabouttext`)

```
Live AI intelligence & deploy signals for CC Operator Decision OS
```

### Long description (`/setdescription`)

```
CC Live Intelligence delivers real-time playbook alerts for the CC Operator Decision OS.

• DEPLOY — execution-ready setups that pass the full TRADE bar (human approval still required before orders)
• WATCH / MONITOR — high-tier research signals; rank ≠ deploy permission

Advisory only · 僅供參考 · Not financial advice.
```

### Commands (`/setcommands`)

```
start - Welcome & setup · 歡迎與設定
status - CC deploy gate & channel status · 部署閘門與頻道狀態
test - Send test alert · 測試推播
help - Command list · 指令說明
```

For in-chat `/start`, `/status`, and `/test` replies without a webhook, run the bot poller (see [Run bot poller](#run-bot-poller) below).

## 1. Create a bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` — suggested name: **TradingAI Alerts CC**, username: `@TradingAI_AlertsCC_bot`.
3. Copy the **HTTP API token** (looks like `123456789:ABC...`).
4. Apply the short/long description and commands above.

## 2. Get your chat ID

**Private chat (simplest)**

1. Send `/start` to your bot.
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

# Deep links — required for "Open in CC" buttons in alerts (tunnel or LAN URL)
# See docs/CC_PUBLIC_ACCESS.md for Cloudflare/ngrok setup
CC_PUBLIC_BASE_URL=https://your-subdomain.trycloudflare.com
```

When `CC_PUBLIC_BASE_URL` is set, all Telegram alerts include an **Open in CC · 開啟 CC** link:

- Opportunity alerts → `{CC_PUBLIC_BASE_URL}/?ticker=NVDA`
- System alerts (deploy gate, BDR, trade gate, regime, circuit breaker) → `{CC_PUBLIC_BASE_URL}`
- Futu capture summary → `{CC_PUBLIC_BASE_URL}`

Without it, alerts still deliver but omit the link button.

Restart the API (`python _cc_instant.py` or `docker compose -f docker-compose.dev.yml up`).

## 4. Verify

```bash
# Status (includes Telegram config, no secrets)
curl -s http://localhost:8000/api/v7/notify/status | python3 -m json.tool

# Setup checklist + BotFather copy-paste text
curl -s http://localhost:8000/api/v7/notify/telegram/setup | python3 -m json.tool

# Professional welcome / test message
curl -s -X POST "http://localhost:8000/api/v7/notify/telegram/test"

# Optional — push description + commands via Bot API
curl -s -X POST http://localhost:8000/api/v7/notify/telegram/configure-profile

# Force opportunity alerts from latest playbook snapshot (testing)
curl -s -X POST "http://localhost:8000/api/v7/notify/telegram/opportunities-now"
```

Live opportunity alerts fire automatically after each **live playbook ranked scan** (background refresh, prewarm, or `GET /api/playbook/ranked?refresh=true`). The first scan only seeds state (no flood); subsequent scans alert on new deploy/monitor names, upgrades, or a new #1 ranked ticker.

## System alerts (AlertService fan-out)

When `TELEGRAM_NOTIFY_SYSTEM=true` (default), these Discord-equivalent events also push to Telegram:

| Event                       | Trigger                                              |
| --------------------------- | ---------------------------------------------------- |
| Deploy gate locked/unlocked | `unlock_deploy` transition in Today/decision refresh |
| BDR decision change         | Board decision code transition                       |
| Trade gate blocked/cleared  | Engine TradeGate hard-block or clear                 |
| Regime change               | RegimeRouter transition                              |
| Circuit breaker             | Hard circuit-breaker triggered                       |

All use the same bilingual CC Live Intelligence format with **Advisory only · 僅供參考** footer.

## Run bot poller

**Root cause of “no reply after /start”:** outbound alerts use `sendMessage` from the CC API process, but **inbound** slash commands require a separate long-polling runner. If only the API container is running, `/start` messages queue in Telegram with no handler.

Webhook setup is optional. For dev, use long polling:

```bash
# Terminal 1 — CC API
python _cc_instant.py

# Terminal 2 — bot poller (reads .env)
python scripts/run_telegram_bot.py
```

Or with Docker Compose (starts API + poller):

```bash
docker compose -f docker-compose.dev.yml up api telegram-bot
```

The poller handles:

| Command   | Behavior                                                    |
| --------- | ----------------------------------------------------------- |
| `/start`  | Welcome + alert types + chat ID setup hint (any chat)       |
| `/status` | `deploy_open` from `/api/v7/decision/board` + notify status |
| `/test`   | Calls `POST /api/v7/notify/telegram/test`                   |
| `/help`   | Command list                                                |

`/status` and `/test` are restricted to `TELEGRAM_CHAT_ID` when set. `/start` always replies and shows your chat ID for `.env` setup.

Legacy path `scripts/dev/telegram_bot_poll.py` delegates to the same runner.

## Alert format preview

**DEPLOY**

```
CC Live Intelligence · 即時情報
━━━━━━━━━━━━━━━━━━━━
🟢 DEPLOY · NVDA
Authority · 部署許可 · Playbook confirmed · TRADE bar passed

Score 8.5 · Tier A · R:R 2.8
Blocker: —
Signal: New opportunity detected · 新機會
🕐 2026-08-25 08:03 UTC
🔗 Open in CC · 開啟 CC

Advisory only · 僅供參考 · Human approval required · CC Operator Decision OS
Confirm bracket/IBKR in CC before sending orders · 下單前請在 CC 確認
```

**WATCH / MONITOR**

```
CC Live Intelligence · 即時情報
━━━━━━━━━━━━━━━━━━━━
👀 WATCH / MONITOR · AMD
Research only · 監控 · NOT deploy permission · 非部署許可 · rank ≠ permission

Score 7.4 · Tier High · R:R 2.1
Blocker: timing not fully confirmed
Why it matters: Near-miss upgrade · 監控升級
🕐 2026-08-25 08:03 UTC
🔗 Open in CC · 開啟 CC

Advisory only · 僅供參考 · Human approval required · CC Operator Decision OS
Monitor only — rank ≠ permission · 僅供監控，排名≠許可
```

## Toggles

| Variable                      | Default | Purpose                                       |
| ----------------------------- | ------- | --------------------------------------------- |
| `TELEGRAM_NOTIFY_ENABLED`     | `true`  | Master switch                                 |
| `TELEGRAM_NOTIFY_DEPLOY`      | `true`  | Deploy-qualified alerts                       |
| `TELEGRAM_NOTIFY_MONITOR`     | `true`  | High-tier WATCH / near-miss                   |
| `TELEGRAM_NOTIFY_SYSTEM`      | `true`  | Deploy gate, BDR, trade gate, regime, breaker |
| `TELEGRAM_ALERT_COOLDOWN_SEC` | `300`   | Dedup window per ticker+tier                  |
| `TELEGRAM_ALERT_DEDUPE`       | `true`  | Enable deduplication                          |

## Security notes

- Never commit real tokens. Use `.env` (gitignored).
- Bot API calls use **HTTPS only** (`api.telegram.org`).
- Logs record success/failure only — tokens are never logged.

See also [CC_PUBLIC_ACCESS.md](CC_PUBLIC_ACCESS.md) for tunnel setup when exposing CC remotely.
