"""Only a provably newer client refuses an older server."""

from __future__ import annotations

import pytest
from any_local_service.version import ServerVersionSkewError, build_identity, check_attach_version


@pytest.mark.parametrize("client,server", [("1+10.gabc", "1+10.gabc"), ("1+9.gdef", "1+10.gabc"), ("1", "1+10.gabc"), ("1+10.gabc", None)])
def test_equal_older_or_undecidable_client_can_attach(client, server):
    check_attach_version(client, server)


def test_newer_client_refuses_with_both_identities():
    with pytest.raises(ServerVersionSkewError, match=r"1\+11.gdef.*1\+10.gabc"):
        check_attach_version("1+11.gdef", "1+10.gabc")


def test_build_identity_takes_injected_build_metadata():
    assert build_identity("1", count=10, commit="abc") == "1+10.gabc"
    assert build_identity("1") == "1"
