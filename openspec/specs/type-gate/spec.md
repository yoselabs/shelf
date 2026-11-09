## Requirements

### Requirement: Project type checking covers editable sources

The project type gate SHALL check Python sources in the configured packages and tools roots even when an editable installation exposes a package source root through interpreter discovery. It SHALL retain the configured strict checks and intentional project exclusions.

#### Scenario: Editable package and tool defects remain visible

- **GIVEN** the root project configuration and a temporary environment exposing an editable package source through a `.pth` file
- **AND** invalid integer assignments in that source, a tool, and an intentionally excluded benchmark runner
- **WHEN** the installed checker runs in project mode
- **THEN** it reports the editable-source and tool assignment errors
- **AND** it reports no diagnostic for the excluded runner
