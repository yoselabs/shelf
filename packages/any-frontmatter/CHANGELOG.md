# any-frontmatter — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.2.0: runtime dependency on atomic-io; `write(path, doc)` unchanged on disk (UTF-8, no newline translation, fsync, same-directory swap, parents created); old file survives a failed write
