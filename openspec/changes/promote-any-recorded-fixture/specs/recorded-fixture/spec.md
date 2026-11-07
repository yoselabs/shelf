## ADDED Requirements

### Requirement: Recorded cases round-trip
The package SHALL record JSON files, optional text and metadata under root/group/case and discover cases sorted.

#### Scenario: Discover recorded exchanges
- **WHEN** a caller records cases across groups
- **THEN** discovery returns their metadata and paths sorted by group then case, ignoring directories without meta.json

### Requirement: Goldens compare and update explicitly
The package SHALL raise GoldenMismatch with a unified diff for differing or missing goldens.

#### Scenario: Replay differs
- **WHEN** actual text differs from the stored golden
- **THEN** the error shows removed and added lines and leaves the golden unchanged

#### Scenario: Update requested
- **WHEN** update is true
- **THEN** actual text replaces the golden

### Requirement: Normalize volatile text
The package SHALL scrub longest nonempty values first and interpret unset, empty and zero update variables as false.

#### Scenario: Overlapping placeholders
- **WHEN** placeholder values overlap
- **THEN** the longest value is replaced first with its uppercase key token
