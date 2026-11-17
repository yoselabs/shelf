## ADDED Requirements

### Requirement: One canonical digest of a JSON value
`digest(value, length=12)` SHALL return the first `length` hex characters of sha256 over the value's JSON with sorted
keys, compact separators and UTF-8, so equal data gives equal digests whatever the key order.

#### Scenario: key order is irrelevant
- **WHEN** two mappings hold the same items in different order
- **THEN** their digests are equal

### Requirement: Refuse what JSON cannot say
`digest` SHALL raise `TypeError` or `ValueError` for a non-JSON type, NaN or infinity, or a non-string key, and
SHALL NOT stringify it.

#### Scenario: a datetime
- **WHEN** a value contains a datetime
- **THEN** `digest` raises `TypeError`

### Requirement: Text digest
`digest_text(text, length=12)` SHALL return the first `length` hex characters of sha256 over the UTF-8 text.
