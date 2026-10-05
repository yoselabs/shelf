## ADDED Requirements

### Requirement: A sidecar opens in WAL with explicit transactions

`connect(target)` SHALL create a file target's parent directory, open in autocommit mode with
WAL and `synchronous=NORMAL`, and SHALL touch no path for `":memory:"`. With `read_only` it SHALL
read the last commit and fail every write. An extension loader that fails SHALL raise
`ExtensionUnavailableError` naming the extension.

#### Scenario: A second process reads the last commit
- **GIVEN** a writer holding an open write transaction on a file with one committed row
- **WHEN** another process opens the file read-only and counts the rows
- **THEN** it reads 1 without waiting

#### Scenario: A failed extension is named
- **WHEN** `connect` is given an extension loader that raises
- **THEN** `ExtensionUnavailableError.extension` is that loader's name

### Requirement: A transaction is immediate and nests as a savepoint

`transaction(conn)` SHALL run `BEGIN IMMEDIATE` … `COMMIT`, and `ROLLBACK` on error; inside an
open transaction it SHALL be a savepoint released or rolled back on its own.

#### Scenario: An inner failure keeps the outer work
- **WHEN** an inner transaction raises inside an outer one that then continues
- **THEN** the outer transaction's rows commit and the inner's do not

### Requirement: A time is fixed-width UTC text

`to_text` SHALL write `YYYY-MM-DD HH:MM:SS.ffffff` in UTC (an aware value converted, a naive one
taken as UTC) and `from_text` SHALL read it back, naive or UTC-aware. Text order SHALL be time
order.

#### Scenario: Text sorts as time
- **WHEN** times including a year below 1000 and a microsecond are sorted by their text
- **THEN** the order equals their time order

### Requirement: Damage is told from busy

`is_corruption(exc)` SHALL be true only for a corrupt database or a file that is not one, never
for busy or locked. `integrity_ok(path)` SHALL check on a fresh connection, and `set_aside(path)`
SHALL move the file with its `-wal` and `-shm` to `.corrupt-<UTC stamp>`.

#### Scenario: Busy is not damage
- **WHEN** a second connection fails to begin a write on a busy file
- **THEN** `is_corruption` is false for that error and true for reading a file that is not a database
