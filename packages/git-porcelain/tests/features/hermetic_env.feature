Feature: Git that answers to the test alone

  Background:
    Given the machine's global git config names "Leaked Name" and runs a failing pre-commit hook
    And a variable points git at another repository

  Scenario: The hermetic env shuts the machine out and keeps git quiet
    Given the hermetic git env with the identity "the author"
    When a repository is made and a file committed
    Then the commit's author is "the author"
    And no hook ran

  Scenario: Without an identity git has none
    Given the hermetic git env with no identity
    When a repository is made
    Then git config "user.name" is unset

  Scenario: A test of hooks turns the quiet set off
    Given the hermetic git env with the identity "the author" and no quiet settings
    And the repository runs a pre-commit hook that refuses
    When a repository is made and a file committed
    Then the commit fails
    And the repository's hook ran

  Scenario: A failing command names git's own error
    Given the hermetic git env with no identity
    When git runs "not-a-command" in a folder
    Then the command fails naming "not-a-command"
