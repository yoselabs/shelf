"""settings-base — package-level unit tests.

Covers ${VAR} interpolation, optional-config-path resolution, and the
secret-stripping YAML source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings
from settings_base import SecretStrippingYamlSource, resolve_config_path, resolve_env_refs

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


# ── resolve_env_refs ──────────────────────────────────────────────────────────


def test_env_ref_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SB_HOST", "db.internal")
    assert resolve_env_refs("host=${SB_HOST}") == "host=db.internal"


def test_env_ref_miss_leaves_literal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SB_MISSING", raising=False)
    assert resolve_env_refs("host=${SB_MISSING}") == "host=${SB_MISSING}"


def test_env_ref_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SB_A", "1")
    monkeypatch.setenv("SB_B", "2")
    monkeypatch.delenv("SB_C", raising=False)
    assert resolve_env_refs("${SB_A}-${SB_B}-${SB_C}") == "1-2-${SB_C}"


def test_env_ref_no_refs_passthrough() -> None:
    assert resolve_env_refs("plain string, no refs") == "plain string, no refs"


# ── resolve_config_path ───────────────────────────────────────────────────────


def test_config_path_env_set_and_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "override.yaml"
    cfg.write_text("k: v", encoding="utf-8")
    monkeypatch.setenv("SB_CONFIG", str(cfg))
    default = tmp_path / "default.yaml"  # not created
    assert resolve_config_path("SB_CONFIG", default) == cfg


def test_config_path_env_set_but_missing_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SB_CONFIG", str(tmp_path / "does-not-exist.yaml"))
    default = tmp_path / "default.yaml"
    default.write_text("k: v", encoding="utf-8")
    # Env override is set but points at a missing file: None, never the default.
    assert resolve_config_path("SB_CONFIG", default) is None


def test_config_path_env_unset_default_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SB_CONFIG", raising=False)
    default = tmp_path / "default.yaml"
    default.write_text("k: v", encoding="utf-8")
    assert resolve_config_path("SB_CONFIG", default) == default


def test_config_path_env_unset_default_missing_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SB_CONFIG", raising=False)
    assert resolve_config_path("SB_CONFIG", tmp_path / "default.yaml") is None


# ── SecretStrippingYamlSource ─────────────────────────────────────────────────


class _Throwaway(BaseSettings):
    secret: str = ""
    kept: str = ""


def test_secret_stripping_source_drops_only_secrets(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("secret: from-yaml\nkept: also-from-yaml\n", encoding="utf-8")
    source = SecretStrippingYamlSource(_Throwaway, exclude={"secret"}, yaml_file=cfg)
    data = source()
    assert "secret" not in data
    assert data["kept"] == "also-from-yaml"


def test_secret_stripping_source_accepts_list_exclude(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("secret: x\nkept: y\n", encoding="utf-8")
    # exclude is a plain Collection, not necessarily a frozenset.
    source = SecretStrippingYamlSource(_Throwaway, exclude=["secret", "absent"], yaml_file=cfg)
    data = source()
    assert "secret" not in data
    assert data["kept"] == "y"
