# CC Public Access (Dev)

Expose the Command Center dashboard (`http://127.0.0.1:8000`) to the internet for demos, mobile testing, or remote collaboration.

**This is for development only.** Do not expose production stacks or real broker credentials.

## How it works

| Layer                    | Binding             | Notes                                   |
| ------------------------ | ------------------- | --------------------------------------- |
| `_cc_instant.py`         | `0.0.0.0:8000`      | LAN-reachable on your machine           |
| `docker-compose.dev.yml` | `8000:8000`         | Docker publishes to all host interfaces |
| Tunnel                   | Cloudflare or ngrok | HTTPS public URL → localhost:8000       |

The dashboard and API are served through `_cc_instant.py` on one port, so a single tunnel covers the full UI.

## Quick start (recommended)

1. **Start CC**

    ```bash
    python _cc_instant.py
    # or
    docker compose -f docker-compose.dev.yml up
    ```

2. **Install a tunnel client** (pick one)

    ```bash
    brew install cloudflared          # preferred — quick tunnel needs no account
    # or
    brew install ngrok/ngrok/ngrok
    ```

3. **Run the expose script**

    ```bash
    chmod +x scripts/dev/expose-cc-public.sh
    ./scripts/dev/expose-cc-public.sh
    ```

4. **Copy the public URL** from the terminal:

    - Cloudflare quick tunnel: `https://<random>.trycloudflare.com`
    - ngrok: `https://<subdomain>.ngrok-free.app` (or your reserved domain)

No credentials are required for Cloudflare **quick tunnels** — a new URL is issued each run.

## Optional config

```bash
cp config/tunnel.env.example config/tunnel.env
# Edit config/tunnel.env — do not commit secrets
```

| Variable                  | Purpose                                       |
| ------------------------- | --------------------------------------------- |
| `TUNNEL_PROVIDER`         | `auto` (default), `cloudflare`, or `ngrok`    |
| `CC_TUNNEL_PORT`          | CC port on host (default `8000`)              |
| `CLOUDFLARE_TUNNEL_TOKEN` | Named/persistent Cloudflare tunnel            |
| `NGROK_AUTHTOKEN`         | ngrok auth token                              |
| `NGROK_DOMAIN`            | Reserved ngrok domain (paid)                  |
| `API_SECRET_KEY`          | Strong key for protected API routes           |
| `CORS_ORIGINS`            | Only if API is called from a different origin |

Telegram push alerts: [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optional `CC_PUBLIC_BASE_URL` for alert links).

## Docker Compose tunnel profile

Run CC + tunnel sidecar together:

```bash
# Quick Cloudflare tunnel (random URL, no token)
docker compose -f docker-compose.dev.yml -f docker-compose.tunnel.yml --profile tunnel up

# Named Cloudflare tunnel (set CLOUDFLARE_TUNNEL_TOKEN in .env)
docker compose -f docker-compose.dev.yml -f docker-compose.tunnel.yml --profile tunnel-token up

# ngrok (set NGROK_AUTHTOKEN in .env)
docker compose -f docker-compose.dev.yml -f docker-compose.tunnel.yml --profile tunnel-ngrok up
```

Watch container logs for the public URL:

```bash
docker logs -f cc_tunnel_cloudflare_quick
```

## LAN access (no tunnel)

CC already binds `0.0.0.0:8000`. On the same Wi‑Fi:

```bash
ipconfig getifaddr en0   # macOS Wi‑Fi IP
# Open http://<your-lan-ip>:8000
```

Firewall must allow inbound TCP 8000 on your machine.

## Security

### Warnings

- **Dev defaults are unsafe on the public internet.** `docker-compose.dev.yml` sets `API_SECRET_KEY=dev-secret-local`.
- **Do not commit** `.env`, `config/tunnel.env`, or tunnel tokens.
- **Do not disable** auth middleware or rate limiting for public exposure.
- **No production secrets** in the dev compose stack (broker keys, Discord tokens, etc.).

### Minimum hardening before sharing a URL

1. Set a strong API key:

    ```bash
    export API_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    ```

2. Restart CC so `_cc_instant.py` injects the new key into the dashboard.

3. Share the tunnel URL only with trusted people; quick-tunnel URLs are unlisted but not secret.

4. Stop the tunnel when done (`Ctrl+C` or `docker compose … down`).

### Auth behavior

- Protected routes require `X-API-Key: <API_SECRET_KEY>` (see `src/api/deps.py`).
- The dashboard embeds the key when served — anyone with the URL can use the UI.
- `/health` and some IBKR polling routes stay open by design.

### CORS

Same-origin access through the tunnel usually works without changes. If you split frontend/API origins, add your tunnel URL to `CORS_ORIGINS`:

```bash
export CORS_ORIGINS="https://your-subdomain.trycloudflare.com"
```

## Troubleshooting

| Issue                              | Fix                                                             |
| ---------------------------------- | --------------------------------------------------------------- |
| `CC is not responding at …/health` | Start `_cc_instant.py` or dev compose first                     |
| `cloudflared not found`            | `brew install cloudflared` or use Docker fallback in the script |
| Blank dashboard over tunnel        | Wait for backend warm-up; check `/health` for `mode=full`       |
| 401 on API calls                   | Set `API_SECRET_KEY` and pass `X-API-Key` header                |

## Public URL formats

| Provider         | URL pattern                                |
| ---------------- | ------------------------------------------ |
| Cloudflare quick | `https://<random-words>.trycloudflare.com` |
| Cloudflare named | Your configured hostname in Zero Trust     |
| ngrok free       | `https://<id>.ngrok-free.app`              |
| ngrok reserved   | `https://<your-domain>.ngrok-free.app`     |
