Feature: Read the error envelope a caller received

  Scenario Outline: The envelope is found wherever the surface put it
    Given a refusal with code "not_found" received as <form>
    When its envelope is read
    Then the envelope's code is "not_found"
    And the envelope's details hold "ref" = "note/7"

    Examples:
      | form                         |
      | an MCP result's structure    |
      | an MCP result's text block   |
      | an HTTP body                 |
      | the body's JSON text         |
      | the bare envelope            |

  Scenario Outline: Something that is not an envelope is said to be one nowhere
    Given <received> received
    When its envelope is read
    Then reading fails with "<said>"

    Examples:
      | received                    | said                     |
      | a body without an error     | no error envelope        |
      | an MCP result with nothing  | neither structured       |
      | a JSON list                 | not a JSON object        |

  Scenario: A refusal with another code fails, naming both
    Given a refusal with code "version_conflict" received as an HTTP body
    When it is asserted refused with "not_found"
    Then the assertion fails with "expected a refusal with 'not_found', got 'version_conflict'"

  Scenario: A success asserted as a refusal fails, saying it succeeded
    Given a call that succeeded
    When it is asserted refused with "not_found"
    Then the assertion fails with "the call succeeded"

  Scenario: The shipped step passes on the refusal it names
    Given a call refused with "invalid_argument"
    Then the call is refused with "invalid_argument"

  Scenario Outline: The shipped step fails on anything else
    Given <call>
    When the shipped step checks for "invalid_argument"
    Then the assertion fails with "<said>"

    Examples:
      | call                              | said                                  |
      | a call that succeeded             | the call succeeded: {'ok': True}      |
      | a call refused with "not_found"   | got 'not_found'                       |
