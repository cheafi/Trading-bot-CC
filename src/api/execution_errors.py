"""Structured execution API errors."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException


def execution_http_error(
    status_code: int, *, code: str, message: str, extra: Dict[str, Any] | None = None
) -> HTTPException:
    body: Dict[str, Any] = {"code": code, "message": message}
    if extra:
        body.update(extra)
    return HTTPException(status_code=status_code, detail=body)
