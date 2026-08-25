"""Runtime truth engine registration for gate snapshots."""

from __future__ import annotations

from unittest import mock

from src.services.runtime_truth import register_engine, registered_engine_breaker


def test_registered_engine_breaker_reads_circuit_breaker():
    cb = mock.Mock(triggered=True, trigger_reason="daily loss")
    engine = mock.Mock(circuit_breaker=cb)
    register_engine(engine)
    snap = registered_engine_breaker()
    assert snap["circuit_breaker"] is True
    assert "daily loss" in snap["circuit_breaker_reason"]


def test_registered_engine_breaker_empty_when_unregistered():
    register_engine(None)
    snap = registered_engine_breaker()
    assert snap["circuit_breaker"] is False
