"""Private context token — only ExecutionGateway may skip ledger intent."""

from __future__ import annotations

import contextvars
from typing import Optional

_GATEWAY_TOKEN: contextvars.ContextVar[Optional[object]] = contextvars.ContextVar(
    "execution_gateway_adapter", default=None
)

_SENTINEL = object()


def enter_gateway_adapter() -> contextvars.Token:
    return _GATEWAY_TOKEN.set(_SENTINEL)


def reset_gateway_adapter(token: contextvars.Token) -> None:
    _GATEWAY_TOKEN.reset(token)


def gateway_adapter_active() -> bool:
    return _GATEWAY_TOKEN.get() is _SENTINEL
