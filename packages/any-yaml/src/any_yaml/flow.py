"""Compact flow-style lines for small mappings: `key: {a: 1, b: [x, y]}`, one line per top-level key, quoted by ruamel
(a value with `"`, `\\`, `: `, a leading `#`, or that reads as a number is quoted correctly, never by hand)."""

import io
from collections.abc import Mapping

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq


def _flow(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = CommentedMap((k, _flow(v)) for k, v in value.items())
        mapping.fa.set_flow_style()
        return mapping
    if isinstance(value, (list, tuple)):
        seq = CommentedSeq(_flow(v) for v in value)
        seq.fa.set_flow_style()
        return seq
    return value


def flow_lines(mapping: Mapping[str, object]) -> str:
    """One line per key in sorted key order, each value a flow mapping or sequence (nested order kept as given).

    The result parses back to `mapping`; every line ends with a newline; empty input gives an empty string."""
    yaml = YAML(typ="rt")
    yaml.width = 10**9
    out = io.StringIO()
    for key in sorted(mapping):
        yaml.dump(CommentedMap([(key, _flow(mapping[key]))]), out)
    return out.getvalue()
