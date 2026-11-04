"""Public API re-exports preserve the identities of result types and records."""

from __future__ import annotations

import pytest

from git_porcelain import api, api_results, plumbing


@pytest.mark.parametrize("name", api_results.__all__)
def test_api_reexports_the_result_types_directly(name: str) -> None:
    assert name in api.__all__
    assert getattr(api, name) is getattr(api_results, name)


def test_plumbing_preserves_its_ref_exports() -> None:
    assert plumbing.Ref is api_results.Ref
    assert plumbing.Refs is api_results.Refs


def test_result_diagnostics_redact_before_truncating_the_tail() -> None:
    output = "start\nhttps://user:password@example.invalid/repo\n" + "detail\n" * 200
    result = api.HookRejected(output)
    assert result.output.startswith("start\nhttps://***@example.invalid/repo\n")
    assert len(result.tail) <= 600
    assert "password" not in result.tail
    assert api.CommandResult(ok=True, output=output).output == result.output
    assert api.RemoteRefs(output=output).output == result.output
    assert api.Refs(output=output).output == result.output
    assert api.RefRejected("https://user:" + "p" * 700 + "@host/repo").tail == "https://***@host/repo"
