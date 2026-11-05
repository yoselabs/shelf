# shelf-vendor — changelog

AI-facing only: one line per contract-shape change, arrow notation. No prose, no rationale
(see the ledger for why). Read this before source/README when reconciling a pin
(agent-loop.md WORKFLOW: RECEIVE).

- 0.1.0: new. `Vendor(vendor_dir, manifest_path)`; `sync(name, tag=None, *, shelf) -> entry`; `check(shelf=None) -> (drift, warnings)`; `tree_hash`, `dir_files`, `tag_files`, `newer_tags`
- 0.1.0: new `python -m shelf_vendor --vendor-dir D --manifest M [--shelf S] sync NAME [--tag T] | check`; manifest `[{name, shelf_tag, shelf_commit, tree_hash}]`
