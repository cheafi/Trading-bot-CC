#!/usr/bin/env bash
# Expose CC (Command Center) at http://127.0.0.1:8000 to the public internet via a dev tunnel.
# Prefers Cloudflare quick tunnel (no account). Falls back to ngrok if configured.
#
# Usage:
#   ./scripts/dev/expose-cc-public.sh              # quick Cloudflare tunnel
#   TUNNEL_PROVIDER=ngrok ./scripts/dev/expose-cc-public.sh
#   cp config/tunnel.env.example config/tunnel.env  # then edit tokens
#
# Requires CC already listening on CC_TUNNEL_PORT (default 8000):
#   python _cc_instant.py
#   # or: docker compose -f docker-compose.dev.yml up
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PORT="${CC_TUNNEL_PORT:-8000}"
PROVIDER="${TUNNEL_PROVIDER:-auto}"
TARGET="http://127.0.0.1:${PORT}"

# Load optional config (never commit secrets)
for f in "$ROOT/config/tunnel.env" "$ROOT/.env"; do
  if [[ -f "$f" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$f"
    set +a
  fi
done

PORT="${CC_TUNNEL_PORT:-$PORT}"
PROVIDER="${TUNNEL_PROVIDER:-$PROVIDER}"
TARGET="http://127.0.0.1:${PORT}"

_red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
_yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
_green() { printf '\033[0;32m%s\033[0m\n' "$*"; }

if [[ "${API_SECRET_KEY:-dev-secret-local}" == "dev-secret-local" ]]; then
  _yellow "WARNING: API_SECRET_KEY is the dev default. Set a strong key before exposing publicly."
  _yellow "  Example: export API_SECRET_KEY=\$(python3 -c \"import secrets; print(secrets.token_urlsafe(32))\")"
fi

if ! curl -sf --max-time 3 "${TARGET}/health" >/dev/null 2>&1; then
  _red "CC is not responding at ${TARGET}/health"
  echo "Start CC first:"
  echo "  python _cc_instant.py"
  echo "  # or: docker compose -f docker-compose.dev.yml up"
  exit 1
fi

_pick_provider() {
  case "$PROVIDER" in
    cloudflare|ngrok) echo "$PROVIDER" ;;
    auto)
      if [[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
        echo cloudflare
      elif [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
        echo ngrok
      else
        echo cloudflare
      fi
      ;;
    *)
      _red "Unknown TUNNEL_PROVIDER=${PROVIDER} (use auto, cloudflare, or ngrok)"
      exit 1
      ;;
  esac
}

PROVIDER="$(_pick_provider)"

_run_cloudflared_local() {
  if [[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
    exec cloudflared tunnel --no-autoupdate run --token "${CLOUDFLARE_TUNNEL_TOKEN}"
  else
    _green "Starting Cloudflare quick tunnel → ${TARGET}"
    _green "Public URL will appear below as https://….trycloudflare.com"
    exec cloudflared tunnel --no-autoupdate --url "${TARGET}"
  fi
}

_run_cloudflared_docker() {
  if [[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
    exec docker run --rm -it \
      -e "TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}" \
      cloudflare/cloudflared:latest \
      tunnel --no-autoupdate run
  else
    _green "Starting Cloudflare quick tunnel (Docker) → host.docker.internal:${PORT}"
    exec docker run --rm -it \
      cloudflare/cloudflared:latest \
      tunnel --no-autoupdate --url "http://host.docker.internal:${PORT}"
  fi
}

_run_ngrok_local() {
  if [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
    _red "NGROK_AUTHTOKEN is required. Get one at https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
  fi
  local args=(http "${PORT}" --authtoken "${NGROK_AUTHTOKEN}")
  if [[ -n "${NGROK_DOMAIN:-}" ]]; then
    args+=(--domain "${NGROK_DOMAIN}")
  fi
  _green "Starting ngrok → ${TARGET}"
  exec ngrok "${args[@]}"
}

_run_ngrok_docker() {
  if [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
    _red "NGROK_AUTHTOKEN is required for ngrok."
    exit 1
  fi
  local domain_arg=()
  if [[ -n "${NGROK_DOMAIN:-}" ]]; then
    domain_arg=(--domain "${NGROK_DOMAIN}")
  fi
  exec docker run --rm -it \
    -e "NGROK_AUTHTOKEN=${NGROK_AUTHTOKEN}" \
    ngrok/ngrok:latest \
    http "host.docker.internal:${PORT}" "${domain_arg[@]}"
}

echo "CC public tunnel — provider: ${PROVIDER}, target: ${TARGET}"
echo "Press Ctrl+C to stop the tunnel."
echo ""

case "$PROVIDER" in
  cloudflare)
    if command -v cloudflared >/dev/null 2>&1; then
      _run_cloudflared_local
    elif command -v docker >/dev/null 2>&1; then
      _run_cloudflared_docker
    else
      _red "Install cloudflared or Docker:"
      echo "  brew install cloudflared"
      echo "  # or: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
      exit 1
    fi
    ;;
  ngrok)
    if command -v ngrok >/dev/null 2>&1; then
      _run_ngrok_local
    elif command -v docker >/dev/null 2>&1; then
      _run_ngrok_docker
    else
      _red "Install ngrok or Docker:"
      echo "  brew install ngrok/ngrok/ngrok"
      exit 1
    fi
    ;;
esac
