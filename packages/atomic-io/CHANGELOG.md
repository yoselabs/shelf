# atomic-io — changelog

AI-facing only: one line per contract-shape change (old ⇒ new).

- 0.3.0: breaking  ⇒  `atomic_write_bytes/text/json(..., keep_mode=False)` lose `keep_mode`; new `atomic_replace_bytes/text/json(path, ..., *, fsync=True)` (the old `keep_mode=True`: the new file gets the permission bits of the file it replaces, the umask default when none); bytes and permissions written are unchanged for every existing call
