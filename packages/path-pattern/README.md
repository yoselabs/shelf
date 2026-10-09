# path-pattern

**Stop caring how a path template runs backwards.** One brace pattern says where a file goes
and, read the other way, what a path found on disk means.

```python
import path_pattern as pp

pp.resolve("{parent_path}/decisions/{n:04}-{slug}.md", {"parent_path": "Projects/136-acme", "n": 14, "slug": "x"})
# 'Projects/136-acme/decisions/0014-x.md'
pp.reverse_match("Projects/{id}-{slug}/README.md", "Projects/140-agent-bootstrap/readme.md")
# {'id': '140', 'slug': 'agent-bootstrap'}
pp.placeholders("{parent_path}/{n:04}-{slug}.md")   # ['parent_path', 'n', 'slug']
pp.pattern_specificity(pattern)                     # literal characters: break multi-match ties
```

## Rules

- Placeholders are `{name}` and `{name:N}`; nothing else is a placeholder.
- `resolve` raises `PatternError` for a missing argument, or a `{name:N}` value that is no
  integer. `{n:04}` pads to four digits and never truncates.
- `reverse_match` returns the captures as strings, or `None`:
  - `{name:N}` matches **at least** N digits, so id 1000 under `{id:03}` reads back, and
    `{n:04}` never claims `12-notes.md`;
  - a name ending in `_path` spans `/`;
  - any other placeholder is one segment, captured lazily: in `{id}-{slug}` the id takes
    the first token and the slug the hyphenated rest.
- Literals match case-insensitively on the way back (`readme.md` for `README.md`); `resolve`
  keeps the pattern's casing.
- Compiled patterns are cached (512): a walk calls `reverse_match` per file per pattern.

Stdlib only.
