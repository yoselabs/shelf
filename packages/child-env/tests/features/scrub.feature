Feature: A child agent gets a scrubbed environment

  Scenario Outline: Variables an agent session exports are removed
    Given the environment has <variable> set to "x"
    When the environment is scrubbed
    Then <variable> is gone

    Examples:
      | variable                 |
      | CLAUDE_CODE_SESSION_ID   |
      | CLAUDE_CONFIG_DIR        |
      | CLAUDE_PLUGIN_DATA       |
      | CLAUDE_PID               |
      | CLAUDECODE               |
      | ANTHROPIC_BASE_URL       |
      | ANTHROPIC_API_KEY        |
      | DELEGATE_LIVE_FILE       |
      | DELEGATE_DEPTH           |
      | MCP_TIMEOUT              |
      | OTEL_EXPORTER_OTLP_ENDPOINT |
      | CODEX_COMPANION_SESSION  |
      | AI_AGENT                 |
      | API_TIMEOUT_MS           |
      | BAGGAGE                  |
      | DISABLE_MICROCOMPACT     |
      | DISABLE_AUTOUPDATER      |
      | USE_STAGING_OAUTH        |
      | USE_LOCAL_OAUTH          |

  Scenario Outline: Credential-looking variables are removed
    Given the environment has <variable> set to "x"
    When the environment is scrubbed
    Then <variable> is gone

    Examples:
      | variable              |
      | OPENAI_API_KEY        |
      | STRIPE_APIKEY         |
      | GH_TOKEN              |
      | GITHUB_TOKEN          |
      | GITHUB_PAT            |
      | AWS_ACCESS_KEY_ID     |
      | AWS_PROFILE           |
      | AWS_SECRET_ACCESS_KEY |
      | DB_PASSWORD           |
      | PGPASSWORD            |
      | CLIENT_SECRET         |
      | GOOGLE_CREDENTIALS    |
      | SSH_PRIVATE_KEY       |
      | SSH_AUTH_SOCK         |
      | my_api_key            |
      | NPM_TOKEN             |

  Scenario Outline: Ordinary variables stay
    Given the environment has <variable> set to "x"
    When the environment is scrubbed
    Then <variable> stays

    Examples:
      | variable           |
      | PATH               |
      | HOME               |
      | LANG               |
      | TERM               |
      | XDG_CONFIG_HOME    |
      | GIT_AUTHOR_NAME    |
      | TASK_LOOP_WORKER   |
      | CLAUDE             |
      | MYCLAUDE_X         |
      | KEYBOARD_LAYOUT    |

  Scenario: keep rescues a name from the defaults
    Given the environment has CLAUDE_CONFIG_DIR set to "/cfg"
    And the environment has GH_TOKEN set to "t"
    When the environment is scrubbed keeping "CLAUDE_CONFIG_DIR"
    Then CLAUDE_CONFIG_DIR stays
    And GH_TOKEN is gone

  Scenario: keep takes a prefix with a trailing star
    Given the environment has MCP_A set to "1"
    And the environment has MCP_B set to "2"
    And the environment has OTEL_X set to "3"
    When the environment is scrubbed keeping "MCP_*"
    Then MCP_A stays
    And MCP_B stays
    And OTEL_X is gone

  Scenario: drop removes the caller's own names
    Given the environment has TASK_LOOP_WORKER set to "1"
    And the environment has TASK_LOOP_SLOT set to "2"
    And the environment has GIT_DIR set to "/g"
    And the environment has PATH set to "/bin"
    When the environment is scrubbed dropping "TASK_LOOP_*, GIT_DIR"
    Then TASK_LOOP_WORKER is gone
    And TASK_LOOP_SLOT is gone
    And GIT_DIR is gone
    And PATH stays

  Scenario: drop wins over keep
    Given the environment has CLAUDE_X set to "1"
    When the environment is scrubbed keeping "CLAUDE_X" and dropping "CLAUDE_X"
    Then CLAUDE_X is gone

  Scenario: Values are carried over unchanged
    Given the environment has PATH set to "/usr/bin:/bin"
    When the environment is scrubbed
    Then PATH is "/usr/bin:/bin"

  Scenario: The input is not mutated
    Given the environment has CLAUDECODE set to "1"
    And the environment has PATH set to "/bin"
    When the environment is scrubbed
    Then the input still has CLAUDECODE and PATH
    And the result is a different dict

  Scenario: The current process environment is scrubbed on request
    Given the process environment has CLAUDECODE set to "1" and CHILD_ENV_MARK set to "m"
    When the current environment is scrubbed
    Then CLAUDECODE is gone
    And CHILD_ENV_MARK stays
