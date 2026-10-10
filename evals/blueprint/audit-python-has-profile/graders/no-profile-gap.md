---
type: regex
target: {source: file, path: docs/blueprint/stack-python-uv.md}
pattern: "^(?![\\s\\S]*stack\\.python-uv\\.profile` \\(blueprint gap\\))[\\s\\S]*$"
---
A stack that has a profile is not reported as a blueprint gap.
