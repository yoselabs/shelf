from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from any_net import Probe, cached, probe, record

if TYPE_CHECKING:
    from pathlib import Path

VENDOR = "api.vendor.test:443"


def _resolver(good: set[str]):
    def resolve(name: str, port: int) -> str:
        if name not in good:
            msg = "no such host"
            raise OSError(msg)
        return "10.0.0.1"

    return resolve


def _connector(refuse: frozenset[str] = frozenset()):
    def connect(addr: tuple[str, int], timeout: float) -> None:
        if addr[0] in refuse:
            msg = "refused"
            raise ConnectionRefusedError(msg)

    return connect


def test_all_reachable_is_up() -> None:
    p = probe([VENDOR], resolve=_resolver({"api.vendor.test"}), connect=_connector(), clock=lambda: 5.0)
    assert (p.up, p.ip_up, p.why, p.at) == (True, True, "ok", 5.0)
    assert p.per_host == {VENDOR: "ok", "1.1.1.1:443": "ok"}


def test_names_failing_while_the_literal_answers_is_dns() -> None:
    p = probe([VENDOR], resolve=_resolver(set()), connect=_connector())
    assert (p.up, p.ip_up, p.why) == (False, True, "dns")
    assert p.per_host[VENDOR] == "dns"


def test_resolving_name_that_refuses_is_vendor() -> None:
    p = probe([VENDOR], resolve=_resolver({"api.vendor.test"}), connect=_connector(frozenset({"10.0.0.1"})))
    assert (p.up, p.ip_up, p.why) == (False, True, "vendor")
    assert p.per_host[VENDOR] == "tcp"


def test_nothing_answering_is_offline() -> None:
    p = probe([VENDOR], resolve=_resolver(set()), connect=_connector(frozenset({"1.1.1.1"})))
    assert (p.up, p.ip_up, p.why) == (False, False, "offline")


def test_default_host_is_the_neutral_name() -> None:
    p = probe(resolve=_resolver({"one.one.one.one"}), connect=_connector())
    assert p.up and "one.one.one.one:443" in p.per_host


def test_a_hung_resolver_is_slow_and_the_call_returns_by_the_deadline() -> None:
    release = threading.Event()

    def hang(name: str, port: int) -> str:
        release.wait(5)
        return "10.0.0.1"

    try:
        p = probe([VENDOR], budget_s=0.2, resolve=hang, connect=_connector())
    finally:
        release.set()
    assert p.per_host[VENDOR] == "slow"
    assert p.ms < 1500
    assert (p.up, p.why) == (False, "offline" if not p.ip_up else "vendor")


def test_cache_round_trip_and_staleness(tmp_path: Path) -> None:
    path = tmp_path / "net.json"
    p = probe([VENDOR], resolve=_resolver({"api.vendor.test"}), connect=_connector(), clock=lambda: 100.0)
    stored = record(path, p)
    assert stored.since == 100.0
    assert cached(path, 120, clock=lambda: 150.0) == stored
    assert cached(path, 120, clock=lambda: 221.0) is None


def test_since_moves_only_when_up_flips(tmp_path: Path) -> None:
    path = tmp_path / "net.json"
    up = lambda at: Probe(True, True, "ok", {}, at)  # noqa: E731
    down = lambda at: Probe(False, True, "dns", {}, at)  # noqa: E731
    record(path, up(10.0))
    assert record(path, up(20.0)).since == 10.0
    assert record(path, down(30.0)).since == 30.0
    assert record(path, down(40.0)).since == 30.0


def test_cached_is_none_for_missing_or_corrupt_file(tmp_path: Path) -> None:
    assert cached(tmp_path / "absent.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert cached(bad) is None


def test_record_never_raises_on_an_unwritable_path(tmp_path: Path) -> None:
    p = Probe(True, True, "ok", {}, 1.0)
    assert record(tmp_path / "no" / "such" / "dir" / "net.json", p).up is True
