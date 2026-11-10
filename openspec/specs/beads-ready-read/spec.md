## Requirements

### Requirement: The ready set keeps the tracker's order and label filter

A ready read SHALL return the tracker's ready records in the tracker's own order, with their scheduling fields decoded. A label SHALL keep only records carrying it, in the same order. No ready record, or no record carrying the label, SHALL return an empty list.

### Requirement: A failed ready read never becomes an empty success

A missing binary, timeout, malformed reply or other backend failure SHALL raise the owning typed error with diagnostic text. A reply that is not a list of records SHALL be malformed, never an empty ready set.

### Requirement: Consumers can exercise the same ready contract with a seeded fake

The owning library SHALL expose a structural ready-set read protocol, extend its semantic in-memory read fake with a seeded ready set and a whole-read fault, and provide a shared contract run against both the fake and the real client. The fake SHALL NOT compute readiness: the caller seeds which records are ready and in which order. Separate fake instances SHALL represent separate backlogs without a process.
