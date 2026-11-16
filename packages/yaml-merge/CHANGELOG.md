# yaml-merge — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: `merge_into(existing, payload: Mapping) -> Mapping`: payload values carried into a `CommentedMap`; a non-mapping `existing` -> `payload` as-is; list entries pair by the first of `name`/`id`/`key` on every entry, else by position.
- 0.2.0: additive  ⇒  `merge_into(existing, payload: list) -> list`: a top-level `CommentedSeq` merges as a nested list does; any other `existing` -> `payload` as-is.
- 0.2.0: additive  ⇒  `merge3(base, ours, theirs) -> object`: three-way merge by structure (mappings key by key, list entries by the same identity keys, required distinct; a list without identity changed on both sides conflicts); `None` = absent/empty document; result carried into `ours` with `merge_into` when it is a ruamel node (comments kept), else plain data; `MergeConflictError(ValueError).path` names where both sides changed one value differently (mapping keys, entry identity values; `()` = the document).
