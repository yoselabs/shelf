Feature: A test sees no LLM provider unless it configures one

  Scenario: The machine's providers disappear
    Given the shell holds "ANTHROPIC_API_KEY", "OPENAI_API_KEY" and "CLAUDE_CODE_OAUTH_TOKEN"
    And the shell holds the consumer's own key "ACME_LLM_KEY"
    When the hermetic LLM env is applied naming "ACME_LLM_KEY"
    Then none of those variables is set
    And the Claude Code CLI and SDK backends report unavailable
    And no provider is selected

  Scenario: A test that configures a provider still gets it
    Given the hermetic LLM env is applied
    When the test sets "OPENAI_API_KEY"
    Then the openai-compatible backend reports available
