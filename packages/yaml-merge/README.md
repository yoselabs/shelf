# yaml-merge

**Stop caring that writing a config back destroys the file its author wrote.**

```python
from ruamel.yaml import YAML
from yaml_merge import merge_into

yaml = YAML(typ="rt")
document = yaml.load(path.read_text())        # what the human wrote
yaml.dump(merge_into(document, model.model_dump()), out)
```

Without the merge, dumping `model.model_dump()` over the file replaces the
document: every comment gone, blank lines gone, the author's key order replaced by
the model's. The file stops being theirs the first time the program touches it.

## The contract

The payload is authoritative about **values**. The existing document is
authoritative about **everything else**.

| survives | changes |
|---|---|
| comments above a key, and trailing on its line | a value the payload changed |
| blank lines and the author's key order | a key the payload added (appended at the end) |
| quoting style, anchors ruamel understands | a key the payload no longer has (removed, with its comment) |

`merge_into(existing, payload)` never mutates `payload`. The payload is a mapping
or a list; an `existing` of another shape — the file was absent, empty, or held
something else — has no document worth preserving, so the payload is returned as
it is. A top-level list merges as a nested one does.

**List entries are paired by identity, then by position.** The first of `name`,
`id`, `key` that is present on *every* entry of both lists is used to match them;
otherwise entries are matched by index. Inserting an entry at the top of a list
would otherwise shift every comment down one.

## Merging two edits: `merge3`

```python
from yaml_merge import MergeConflictError, merge3

merged = merge3(yaml.load(base), yaml.load(ours), yaml.load(theirs))   # rt nodes
yaml.dump(merged, out)                                                 # ours' comments kept
```

Git merges YAML by line, so two branches appending to one list conflict. `merge3`
merges by structure: a value only one side changed takes the change, mappings merge
key by key, and list entries pair by the same identity keys as above (each value
distinct on each side). A list without identity that both sides changed is a
conflict: position does not say which entry is which. Where both sides changed one
value differently it raises `MergeConflictError`, whose `path` names it from the root
(mapping keys, and an entry's identity value). `None` is an absent or empty file.

The merged values are carried into `ours` with `merge_into`, so its comments,
blank lines and key order survive; `base` and `theirs` are never mutated. This is
the core of a Git merge driver for YAML files whose entries carry an identity.

## What this is not for

A reader that never leaves ruamel's `CommentedMap` — parse, mutate in place, dump.
There the comments never left, and there is nothing to merge. This is for the other
shape: values that round-trip through something which cannot carry a comment (a
pydantic model, a dataclass, a plain `dict`) and have to be put back.

## Two things ruamel does that a naive merge gets wrong

Both are pinned by tests here, and both were found the hard way.

**A comment above a key is filed under the *previous* key.** So `del doc[key]`
removes the key and leaves the paragraph explaining it sitting above whatever comes
next — worse than no comment, because it reads as current. Cutting it means
splitting the previous key's comment token, whose first line may be that key's own
end-of-line comment.

**Slice assignment on a `CommentedSeq` clears its comment map,** and that map is
keyed by *index*. Rebuilding a list therefore drops every entry comment — or, if
you restore the map naively, gives each entry the comment belonging to whatever now
sits at its old position.
