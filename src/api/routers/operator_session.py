"""Same-origin operator session — avoids embedding API_SECRET_KEY in HTML."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field

from src.api.deps import (
    OPERATOR_SESSION_COOKIE,
    OPERATOR_SESSION_MAX_AGE_S,
    mint_operator_session_token,
    verify_operator_session_token,
)

router = APIRouter(tags=["operator"])


class OperatorSessionRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=512)


def _load_secret() -> str:
    from src.api.deps import _load_settings

    settings = _load_settings()
    secret = (settings.api_secret_key or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set API_SECRET_KEY.",
        )
    return secret


@router.post("/api/operator/session")
async def establish_operator_session(body: OperatorSessionRequest, response: Response):
    """Validate operator API key and set HttpOnly session cookie (trusted LAN / same-origin)."""
    secret = _load_secret()
    if not hmac.compare_digest(body.api_key.strip(), secret):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    token = mint_operator_session_token(secret)
    response.set_cookie(
        key=OPERATOR_SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=OPERATOR_SESSION_MAX_AGE_S,
        path="/",
    )
    return {"ok": True, "authenticated": True, "expires_in_seconds": OPERATOR_SESSION_MAX_AGE_S}


@router.delete("/api/operator/session")
async def clear_operator_session(response: Response):
    response.delete_cookie(key=OPERATOR_SESSION_COOKIE, path="/")
    return {"ok": True, "authenticated": False}


@router.get("/api/operator/session/status")
async def operator_session_status(
    cc_operator_session: str | None = Cookie(None, alias=OPERATOR_SESSION_COOKIE),
):
    """Non-sensitive session probe for dashboard bootstrap."""
    try:
        secret = _load_secret()
    except HTTPException:
        return {"authenticated": False, "reason": "api_key_not_configured"}
    return {
        "authenticated": verify_operator_session_token(secret, cc_operator_session),
    }
