# shelf-vendor

**One tool to vendor shelf packages into a plugin.** Git-pinned dependencies do not work for a plugin's skill
directory, so a plugin copies package source. This replaces the two diverging `dev/vendor.py` files. Standard
library only. **Sunset:** remove it, and every `_vendor/` directory, when plugins can depend on the shelf directly.

```bash
export PYTHONPATH=$SHELF/packages/shelf-vendor/src          # or vendor shelf-vendor itself
python3 -m shelf_vendor --vendor-dir skills/x/_vendor --manifest dev/vendor.json sync process-lock --tag process-lock-v0.2.0
python3 -m shelf_vendor --vendor-dir skills/x/_vendor --manifest dev/vendor.json check
```

```python
from shelf_vendor import Vendor
v = Vendor(vendor_dir, manifest_path)
v.sync("process-lock", "process-lock-v0.2.0", shelf=shelf)   # tag omitted: the recorded one
drift, warnings = v.check(shelf)                             # shelf omitted: manifest check only
```

## Rules

- **Byte-identical.** `sync` reads the files with `git archive` from the tag, never the working tree, replaces the
  vendored directory (named by import name) and records `{name, shelf_tag, shelf_commit, tree_hash}`.
- **tree_hash.** sha256 over each file in sorted POSIX path order: path, NUL, byte length, NUL, bytes;
  `__pycache__` and `*.pyc` skipped.
- **`check` fails** (exit 1) on a missing copy, a copy whose hash differs from the manifest, and (with a shelf) a tag whose own
  content differs from the manifest. A **newer shelf tag** (`<package>-vX.Y.Z`, or any not contained in a recorded bare
  commit) is only a warning on stderr.
- **Shelf checkout:** `--shelf`, else `$SHELF_HOME`, else `~/Workspaces/shelf`.
