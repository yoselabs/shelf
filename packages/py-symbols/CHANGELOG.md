# Changelog

## 0.2.0

- Depends on `content-digest>=0.2,<1`; `symbol_hash` is `digest_text(span.text, length=length)`, the same prefix as before. `length` outside 1..64 now raises ValueError (before: 0 gave "", above 64 gave all 64).

## 0.1.0

- `find`, `functions`, `innermost`, `symbol_hash` over the stdlib `ast`. Promoted from ogy's evidence and locate modules.
