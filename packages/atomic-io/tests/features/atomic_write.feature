Feature: A file is written whole or not at all

  Scenario: A JSON write replaces the old file in one step
    Given a file "state.json" holding the JSON {"n": 1}
    When the JSON {"n": 2, "name": "é"} is written atomically to "state.json"
    Then "state.json" holds the JSON {"n": 2, "name": "é"}
    And no temp file is left beside it

  Scenario: A write that cannot be encoded leaves the old file alone
    Given a file "state.json" holding the JSON {"n": 1}
    When a value JSON cannot encode is written atomically to "state.json"
    Then the write is refused
    And "state.json" holds the JSON {"n": 1}
    And no temp file is left beside it

  Scenario: keep_mode carries the permissions of the file replaced
    Given a file "secret.bin" with permissions 640
    When the bytes "new" are written atomically to "secret.bin" keeping its mode
    Then "secret.bin" has permissions 640
    And "secret.bin" holds the bytes "new"

  Scenario: Without keep_mode the file is private to the owner
    Given a file "secret.bin" with permissions 644
    When the bytes "new" are written atomically to "secret.bin"
    Then "secret.bin" has permissions 600

  Scenario: Skipping fsync still swaps whole
    When the bytes "fast" are written atomically to "cache.bin" without fsync
    Then "cache.bin" holds the bytes "fast"
