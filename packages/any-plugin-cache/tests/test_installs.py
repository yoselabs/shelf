"""Installed versions, pins and rollback over a fake claude dir."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from any_plugin_cache import behind, installed_version, installs, pin_ok, previous, version_key

MARK = "skills/x/x.py"
Install = Callable[..., Path]
Record = Callable[[dict[str, object]], None]


def test_lists_only_complete_versioned_dirs(claude: Path, install: Install) -> None:
    a = install("0.9.1")
    install("0.23.56")
    install("0.5.0", marker=None)  # half-copied: no marker
    install("latest")  # not a version
    install("0.1.0", plugin="other")
    assert installs(claude, "p", MARK).keys() == {"0.9.1", "0.23.56"}
    assert installs(claude, "p", MARK)["0.9.1"] == a


def test_no_cache_is_empty(claude: Path) -> None:
    assert installs(claude, "p", MARK) == {}


def test_versions_order_numerically_not_lexically() -> None:
    assert version_key("0.23.56") > version_key("0.9.1")  # type: ignore[operator]
    assert version_key("1.0") is None or version_key("1.0") == (1, 0)
    assert version_key("1.0-rc") is None
    assert version_key("") is None


def test_installed_version_reads_user_scope(claude: Path, record: Record) -> None:
    record(
        {
            "p@m": [
                {"scope": "project", "installPath": "/x/p/0.1.0"},
                {"scope": "user", "installPath": "/c/plugins/cache/m/p/0.23.56"},
            ]
        }
    )
    assert installed_version(claude, "p") == "0.23.56"
    assert installed_version(claude, "q") == ""


def test_installed_version_is_blank_without_or_with_broken_record(claude: Path, record: Record) -> None:
    assert installed_version(claude, "p") == ""
    (claude / "plugins").mkdir(parents=True)
    (claude / "plugins" / "installed_plugins.json").write_text("{nope", encoding="utf-8")
    assert installed_version(claude, "p") == ""
    record({"p@m": "not a list"})
    assert installed_version(claude, "p") == ""


def test_pin_must_name_an_installed_dir(claude: Path, install: Install) -> None:
    install("0.2.0")
    found = installs(claude, "p", MARK)
    assert pin_ok(found, "0.2.0")
    assert not pin_ok(found, "0.3.0")


def test_previous_is_newest_below_current(claude: Path, install: Install) -> None:
    for v in ("0.9.1", "0.23.5", "0.23.56", "0.30.0"):
        install(v)
    found = installs(claude, "p", MARK)
    assert previous(found, "0.23.56") == "0.23.5"
    assert previous(found, "0.30.0") == "0.23.56"
    assert previous(found, "0.9.1") == ""
    assert previous(found, "0.10.0") == "0.9.1"  # current need not be installed


def test_behind_counts_newer_installs(claude: Path, install: Install) -> None:
    for v in ("0.1.0", "0.2.0", "0.3.0"):
        install(v)
    found = installs(claude, "p", MARK)
    assert behind(found, "0.1.0") == 2
    assert behind(found, "0.3.0") == 0
    assert behind(found, "junk") == 0
