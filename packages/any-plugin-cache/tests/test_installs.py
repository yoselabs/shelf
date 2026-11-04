"""Installed versions, pins and rollback over a fake claude dir."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from any_plugin_cache import behind, installed_version, installs, previous, rollback_target, version_key

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


def test_pin_check_is_membership(claude: Path, install: Install) -> None:
    install("0.2.0")
    found = installs(claude, "p", MARK)
    assert "0.2.0" in found
    assert "0.3.0" not in found


def test_dir_with_main_file_but_no_manifest_is_not_installed(claude: Path, install: Install) -> None:
    install("0.1.0")
    half = install("0.2.0")
    (half / ".claude-plugin").mkdir()  # no plugin.json inside
    both = (MARK, ".claude-plugin/plugin.json")
    assert installs(claude, "p", both) == {}
    (install("0.3.0") / ".claude-plugin").mkdir()
    done = claude / "plugins" / "cache" / "m" / "p" / "0.3.0" / ".claude-plugin" / "plugin.json"
    done.write_text("{}", encoding="utf-8")
    assert installs(claude, "p", both).keys() == {"0.3.0"}
    assert installs(claude, "p", MARK).keys() == {"0.1.0", "0.2.0", "0.3.0"}


def test_plugin_name_is_not_a_glob(claude: Path, install: Install) -> None:
    install("0.1.0", plugin="a")
    install("0.1.0", plugin="b")
    assert installs(claude, "*", MARK) == {}
    assert installs(claude, "[ab]", MARK) == {}


def test_previous_of_an_unparseable_current_is_blank(claude: Path, install: Install) -> None:
    install("0.1.0")
    assert previous(installs(claude, "p", MARK), "junk") == ""


def test_rollback_target_picks_current_from_pin_then_record_then_newest(claude: Path, install: Install) -> None:
    for v in ("0.1.0", "0.2.0", "0.3.0"):
        install(v)
    found = installs(claude, "p", MARK)
    assert rollback_target(found, pinned="0.2.0", installed="0.3.0") == ("0.1.0", "")
    assert rollback_target(found, installed="0.3.0") == ("0.2.0", "")
    assert rollback_target(found) == ("0.2.0", "")


def test_rollback_target_says_why_not(claude: Path, install: Install) -> None:
    assert rollback_target({}) == ("", "no install to roll back from")
    install("0.1.0")
    assert rollback_target(installs(claude, "p", MARK)) == ("", "no version older than 0.1.0 is installed")


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
