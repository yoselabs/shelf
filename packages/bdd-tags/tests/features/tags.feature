Feature: Tags a Gherkin suite reads rather than runs

  Scenario Outline: A tagged scenario's outcome
    Given a feature whose scenario <body> is tagged "<tag>"
    When the suite runs with strict markers
    Then the scenario is reported as <outcome>

    Examples:
      | body   | tag                   | outcome |
      | passes | @spec:entity-crud     | passed  |
      | passes | @bug:proj-12          | passed  |
      | fails  | @known_bug:proj-40    | xfailed |
      | passes | @known_bug:proj-40    | failed  |
      | fails  | @pending              | skipped |
      | passes | @unregistered         | errored |

  Scenario: A missing step without @pending still fails
    Given a feature whose scenario has a step nobody wrote
    When the suite runs with strict markers
    Then the scenario is reported as failed
