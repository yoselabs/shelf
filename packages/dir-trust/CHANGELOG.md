# dir-trust — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.3.0: grant keys come from `any_file.path_key` (same resolved text; store bytes unchanged); requires `any-file>=0.3,<1`
- 0.2.0: runtime dependency on atomic-io; store bytes unchanged (YAML dump, UTF-8); a failed write still raises TrustStoreError and leaves the old store
