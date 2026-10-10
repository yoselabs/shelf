Feature: Drive an MCP server as its clients do

  Background:
    Given a server with a counter, an echo and a tool that refuses

  Scenario: The agent calls a tool with its arguments as JSON
    When the agent calls "echo" with:
      """
      {"said": "Harbor migration"}
      """
    Then the result holds "said" = "Harbor migration"
    And the result has no notices
    And there is no refusal

  Scenario: Someone else is a second session on the same server
    Given the agent calls "count" with:
      """
      {}
      """
    When someone else calls "count" with:
      """
      {}
      """
    Then the result holds "count" = "2"
    And the agent and someone else hold different sessions

  Scenario: A refusal is kept, never raised, and the next success clears it
    When the agent calls "refuse" with:
      """
      {"code": "not_found"}
      """
    Then the refusal's code is "not_found"
    And there is no result
    When the agent calls "echo" with:
      """
      {"said": "back"}
      """
    Then there is no refusal
    And the result holds "said" = "back"

  Scenario: Text blocks after the first are notices
    When the agent calls "notice" with:
      """
      {}
      """
    Then the result's notices are "the vault is read-only"

  Scenario: A suite's prepare fills the arguments before the call
    Given the suite fills "$name" with "Acme"
    When the agent calls "echo" with:
      """
      {"said": "$name"}
      """
    Then the result holds "said" = "Acme"

  Scenario: A refusal in plain text keeps its message
    When the agent calls "refuse_plainly" with:
      """
      {}
      """
    Then the refusal's message is "nothing to do"

  Scenario: Asking keeps nothing
    Given the agent calls "echo" with:
      """
      {"said": "kept"}
      """
    When an observer asks "refuse" with code "conflict"
    Then the observer saw the refusal "conflict"
    And the result holds "said" = "kept"
