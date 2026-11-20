---
type: regex
target: {source: file, path: .github/workflows/check.yml}
pattern: "uses: actions/checkout@"
---
The audit changes nothing outside docs/blueprint: the workflow is still there as written.
