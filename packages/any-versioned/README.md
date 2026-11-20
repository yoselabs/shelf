# any-versioned

**Stop hand-writing the stored-version check.** A stored JSON format has a version; the reader must know which versions it can read,
turn an old body into the current one, refuse the rest with one error, and stamp the current version when it writes. `Versioned` is that, once.

```python
from any_versioned import UnknownVersionError, Versioned

FORMAT = Versioned(current=2, migrations={1: v1_body_to_v2})    # v1_body_to_v2: dict -> dict

doc = FORMAT.stamp(body)         # {"version": 2, **body}: the version key first, nothing else moves
body = FORMAT.read(loaded)       # the current body, the key removed; a v1 document is migrated first
                                 # raises UnknownVersionError ("... readable: 1, 2; current: 2") for a missing, unknown or newer version
```

The value is the whole check: key lookup, readable set, ordered migrations, the refusal and the stamp. The default view is the pair `stamp` / `read`;
`readable` lists what is accepted. `key=` names the version field (`"version"` by default, `"v"` for a store that already uses it), so no existing file changes where its version sits.

| rule | |
|---|---|
| readable set | every migration source plus `current`; sources run without a gap up to `current - 1`, else `ValueError` at construction |
| refused | a missing key, a non-integer (a bool too), an unlisted number, a newer one; `UnknownVersionError` is a `ValueError` |
| a migration | `body at n -> body at n+1`; steps run in order; the loaded document is not changed |

Not here: SQL schema steps (sqlite-store owns those), content hashes, a foreign tool's own version field. Stdlib only.
