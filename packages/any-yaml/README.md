# any-yaml

**Stop caring how ruamel is configured to read, write and append YAML that people and Git merge.**
Composes [yaml-merge](../yaml-merge/README.md) (comment-keeping write, three-way merge) and
[atomic-io](../atomic-io/README.md) (crash-safe file replace) over ruamel.yaml.

```python
from any_yaml import load, read, dump, merge_text, merge3_text, flow_lines, append_item, write, append_item_file

load("on: yes\n")                         # {"on": "yes"}: safe, YAML 1.2, a fresh copy to change
read(text)                                # cached per content, read-only (dicts are MappingProxyType, lists tuples)
dump({"a": 1})                            # canonical block style, one field per line
merge_text(existing, data)                # data over the author's document; comments, blank lines, key order stay
merge3_text(base, ours, theirs)           # three-way merge by entry id; None when the result is gone
flow_lines({"a/1": {"own": "x", "covers": ["p"]}})
                                          # "a/1: {own: x, covers: [p]}\n", one sorted line per key, quoting by ruamel
append_item(text, "items", {"id": "c"})   # add to a top-level block list; text above the new item is untouched
write(path, data)                         # merge_text into the file (or dump when new), atomically
append_item_file(path, "items", item, initial="format: 1\n")
```

## Contract

- `load` and `read` raise `YAMLError` on malformed text. `read` is for hot paths that only look; change nothing in it.
- `flow_lines` round-trips: `load(flow_lines(m)) == m` for any text, including `"`, `\`, `: `, a leading `#`, and
  words that look like numbers. Only the top level is sorted; nested order is kept as given.
- `append_item` never rewrites earlier text (the result starts with the old text up to the end of the list); item
  lines take the list's existing indentation. It raises `TypeError` when the key holds a non-list, `ValueError` for a flow list
  with items (`[a, b]`); a missing key, `key:` and `key: []` start a new block list.
- `write` and `append_item_file` replace the file atomically and keep its mode; parents are created.
- `MergeConflictError` (from yaml-merge) and `YAMLError` are re-exported.
