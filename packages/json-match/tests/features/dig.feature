Feature: Read a value at a dotted path

  Scenario Outline: A path reads into objects and lists
    Given the value:
      """
      {"user": {"status": "active", "tags": ["a", "b"]}, "items": [{"ref": "note/1"}, {"ref": "note/2"}], "gone": null}
      """
    When the path "<path>" is read
    Then the value read is <read>

    Examples:
      | path          | read                     |
      | user.status   | "active"                 |
      | user.tags.0   | "a"                      |
      | user.tags.-1  | "b"                      |
      | items.*.ref   | ["note/1", "note/2"]     |
      | items.1.ref   | "note/2"                 |
      | gone          | null                     |
      |               | the whole value          |

  Scenario Outline: A path that leads nowhere is missing, not null
    Given the value:
      """
      {"user": {"tags": ["a"]}, "count": 3}
      """
    When the path "<path>" is read
    Then the value read is missing

    Examples:
      | path         |
      | nobody       |
      | user.tags.1  |
      | user.tags.-2 |
      | count.digits |
      | user.tags.x  |

  Scenario: A star over something that is not a list is an error
    Given the value:
      """
      {"user": {"status": "active"}}
      """
    When the path "user.*" is read
    Then the read fails with "* on a dict"
