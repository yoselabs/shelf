# managed-region

**An idempotent, prose-preserving machine-owned block between markers.** The
direnv/terraform/`~/.*rc` "managed block" pattern, marker-agnostic: given a document,
a start marker, and an end marker, write machine-owned content between the markers
and leave the human prose outside them untouched.

```python
from managed_region import replace_region

replace_region(
    body,
    "generated content",
    start_marker="<!-- BEGIN GENERATED -->",
    end_marker="<!-- END GENERATED -->",
)
```

- Re-running with the same content is idempotent — the region is replaced, never
  stacked — and the document always holds exactly one marker pair.
- Structure only: the caller owns the markers and the escape format. Pass an
  `escape` callback when markers could appear inside the content (converted or
  untrusted input) so embedded text can't introduce a corrupting second pair.

## Boundary

Imports no consumer app (`a2web`, `a2kay`) — enforced by `tests/test_boundary_managed_region.py`.
