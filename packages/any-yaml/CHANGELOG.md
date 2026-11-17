# any-yaml — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.1.0: new  ⇒  `load(text)` safe YAML 1.2, fresh; `read(text)` cached, frozen (dict -> MappingProxyType, list -> tuple); `dump(data)` canonical block; `merge_text(existing, data)`, `merge3_text(base, ours, theirs)` over yaml-merge; `flow_lines(mapping)` one flow mapping per sorted key; `append_item(text, key, item)`; `write(path, data)` and `append_item_file(path, key, item, *, initial="")` atomic; `YAMLError`, `MergeConflictError` re-exported.
