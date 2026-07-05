"""Execution guard helpers — circuit breaker must not false-trip on object presence."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.execution_guards import circuit_breaker_tripped, engine_is_running


class _BreakerTripped:
    triggered = True


class _BreakerIdle:
    triggered = False


def test_circuit_breaker_none_engine():
    assert circuit_breaker_tripped(None) is False


def test_circuit_breaker_bool_true():
    assert circuit_breaker_tripped(SimpleNamespace(circuit_breaker=True)) is True


def test_circuit_breaker_bool_false():
    assert circuit_breaker_tripped(SimpleNamespace(circuit_breaker=False)) is False


def test_circuit_breaker_object_not_truthy_by_presence():
    """Legacy bug: bool(breaker_object) was always True."""
    assert circuit_breaker_tripped(SimpleNamespace(circuit_breaker=object())) is False


def test_circuit_breaker_triggered_attr():
    assert circuit_breaker_tripped(SimpleNamespace(circuit_breaker=_BreakerTripped())) is True
    assert circuit_breaker_tripped(SimpleNamespace(circuit_breaker=_BreakerIdle())) is False


def test_circuit_breaker_triggered_flag_on_engine():
    assert circuit_breaker_tripped(SimpleNamespace(circuit_breaker_triggered=True)) is True


def test_engine_is_running():
    assert engine_is_running(None) is False
    assert engine_is_running(SimpleNamespace(_running=False)) is False
    assert engine_is_running(SimpleNamespace(_running=True)) is True
