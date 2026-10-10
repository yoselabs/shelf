Feature: An embedder for tests that loads no model

  Scenario Outline: A vector depends only on its text
    Given a hash embedder of <dim> dimensions
    When "<a>" and "<b>" are embedded as documents
    Then each vector has <dim> numbers and unit length
    And the two vectors are <same>

    Examples:
      | dim  | a              | b                | same      |
      | 384  | harbor         | harbor           | equal     |
      | 384  | harbor         | Harbor           | different |
      | 1024 | the ops team   | the ops team     | equal     |
      | 8    | acme           | acme migration   | different |

  Scenario: A query lands where the same document did
    Given a hash embedder of 16 dimensions
    When "harbor migration" is embedded as a document and as a query
    Then the two vectors are equal

  Scenario: It is an Embedder
    Given a hash embedder of 16 dimensions
    Then it satisfies the Embedder protocol with model id "hash"
