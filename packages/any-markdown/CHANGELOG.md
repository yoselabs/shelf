# Changelog

## 0.6.0

- Breaking: `anchors=` is gone from `outline`, `find` and `Markdown.section`; `Markdown.outline` is gone (it was `.sections`). GitHub's ids are their own views: `github_outline(text)` and `Markdown.github_sections`; look one up with `find(text, id, rows=...)`.

## 0.5.0

- `# Any: <reason>` on the public signature that names `Any`; no behaviour or stored byte changes (shelf public-any rule, tests/test_arch_public_any.py)

## 0.4.0

- `Markdown.outline(anchors="github")` and `Markdown.section(id, anchors="github")` (also `outline(text, anchors=)`, `find(..., anchors=)`): section ids as GitHub anchors them, `github_slug(heading)`, repeats numbered `-1`, `-2`. The default ids are unchanged.
