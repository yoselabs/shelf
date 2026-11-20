# llm-wobble changelog

AI-facing only: one line per contract-shape change (old ⇒ new).

- 0.6.0: breaking  ⇒  `strip_fenced_blocks(text, *, json_only=True)` removed: `strip_fenced_json(text)` (blocks opening `[` or `{`; the old default) and `strip_all_fenced_blocks(text)` (every block; the old `json_only=False`); `parse_list_with_policy(..., strip_fences=True)` loses `strip_fences` (fence stripping always runs; a no-op on fence-free text)
