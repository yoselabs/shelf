"""The derived ontology indexes must always match their source *.toml files.

Constitution I: files are truth; indexes are DERIVED, never hand-edited. This test
fails if catalog/ledger/use-cases READMEs drift from the manifests — run `just catalog`.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

import catalog  # noqa: E402  -- path-injected tool module, imported after sys.path setup


def test_ontology_indexes_are_fresh() -> None:
    for path, expected in catalog.projections().items():
        assert path.exists(), f"{path} missing — run `just catalog`"
        assert path.read_text() == expected, f"{path} is stale — run `just catalog`"


def test_no_orphaned_software() -> None:
    # Every catalogued piece must have at least one active use-case, or it is a
    # decay candidate (Article VIII). At the founding set, all four are consumed by a2kay.
    use_cases = catalog.load(_ROOT / "use-cases")
    for manifest in catalog.load(_ROOT / "catalog"):
        consumers = catalog._active_consumers(str(manifest["name"]), use_cases)
        assert consumers, f"{manifest['name']} is orphaned — no active use-case (Article VIII)"
