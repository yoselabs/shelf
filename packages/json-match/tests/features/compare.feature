Feature: Compare a value with the text a step quoted

  Scenario Outline: A value compares by its text
    Given the value:
      """
      <value>
      """
    Then the value <op> "<text>" is <outcome>

    Examples:
      | value              | op               | text                 | outcome |
      | "active"           | is               | active               | true    |
      | "active"           | is not           | done                 | true    |
      | true               | is               | true                 | true    |
      | 22                 | is               | 22                   | true    |
      | ["c/31", "c/32"]   | is               | c/31, c/32           | true    |
      | ["c/31", "c/32"]   | is               | c/32, c/31           | false   |
      | {"a": 1}           | is               | {"a": 1}             | true    |
      | "harbor migration" | starts with      | harbor               | true    |
      | "harbor migration" | ends with        | migration            | true    |
      | "harbor migration" | contains         | bor mig              | true    |
      | "harbor migration" | does not contain | acme                 | true    |
      | ["acme", "harbor"] | contains         | arb                  | true    |
      | ["acme", "harbor"] | does not contain | ops                  | true    |
      | ["acme", "harbor"] | contains         | acme, harbor         | false   |
      | 22                 | is more than     | 21.5                 | true    |
      | "22"               | is more than     | 22                   | false   |
      | ""                 | is               |                      | true    |

  Scenario: An operator outside the list is an error
    Given the value:
      """
      "active"
      """
    Then comparing with "resembles" fails with "unknown operator"
