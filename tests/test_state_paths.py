"""Authoritative runtime state lives under data/, never /tmp."""

from __future__ import annotations

import inspect
from pathlib import Path

from src.brokers.broker_manager import BrokerManager
from src.core.state_paths import (
    deployment_manifest_path,
    engine_heartbeat_path,
    runtime_state_dir,
    simulation_ledger_path,
    yfinance_cache_dir,
)


def test_runtime_state_dir_defaults_to_data_state(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("STATE_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    path = runtime_state_dir()
    assert path == Path("data/state")
    assert "/tmp" not in str(path)


def test_simulation_ledger_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = simulation_ledger_path()
    assert path == Path("data/simulation_ledger.jsonl")
    assert "/tmp" not in str(path)


def test_yfinance_cache_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("YFINANCE_CACHE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    path = yfinance_cache_dir()
    assert path == Path("data/cache/yfinance")
    assert "/tmp" not in str(path)


def test_deployment_manifest_under_data_state(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("STATE_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    path = deployment_manifest_path()
    assert path.parent == Path("data/state")
    assert "/tmp" not in str(path)


def test_engine_heartbeat_under_data_state(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("STATE_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    path = engine_heartbeat_path()
    assert path.parent == Path("data/state")
    assert "/tmp" not in str(path)


def test_place_order_dry_run_is_keyword_only() -> None:
    params = inspect.signature(BrokerManager.place_order).parameters
    assert params["dry_run"].kind is inspect.Parameter.KEYWORD_ONLY
