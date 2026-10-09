# dir-trust

**Stop caring how a folder earns trust on this machine.** Code that arrived with a
folder — a cloned repository, a synced vault — stays inert until someone here grants it,
and any change to that code takes the grant away again, direnv-style.

```python
from dir_trust import TrustStore, folder_hash

store = TrustStore(config_home / "trust.yml")   # outside the folder it vouches for
store.grant(vault, vault / "jobs", pattern="*.py")
store.is_trusted(vault, vault / "jobs", pattern="*.py")   # False after any edit
store.revoke(vault)                                       # True when there was a grant
```

## Rules

- **The grant is a hash.** SHA-256 over the matching files in name order, each file's
  bytes after its name and a NUL. Editing, adding or removing a matching file changes
  it, so the old grant stops matching with no one revoking it. Not recursive; a folder
  that matches the pattern is skipped. A missing or empty folder has one fixed digest.
- **The key is resolved.** Two spellings of one path share a grant.
- **Written atomically.** A torn write would make every granted folder look untrusted.
- **Unusable store is an error, not a refusal.** A store that exists but will not parse
  or write raises `TrustStoreError(path)`; the caller decides what that means. A store
  that does not exist yet is empty.
- The store is plain YAML, `{key: digest}`, so an operator can read it.
