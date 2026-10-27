Feature: An app's folders are decided once

  Scenario Outline: Each kind of folder follows its XDG variable
    Given the environment sets <variable> to "<value>"
    When the <kind> folder of "task-loop" is asked for
    Then the folder is "<folder>"

    Examples:
      | kind   | variable        | value    | folder                 |
      | config | XDG_CONFIG_HOME | /cfg     | /cfg/task-loop         |
      | state  | XDG_STATE_HOME  | /st      | /st/task-loop          |
      | cache  | XDG_CACHE_HOME  | /ca      | /ca/task-loop          |
      | state  | XDG_CONFIG_HOME | /cfg     | /home/me/.local/state/task-loop |
      | cache  | XDG_CACHE_HOME  | relative | /home/me/.cache/task-loop |

  Scenario: A plugin's data folder wins only when asked for
    Given the environment sets CLAUDE_PLUGIN_DATA to "/plugins/data/x"
    When the config folder of "task-loop" is asked for
    Then the folder is "/home/me/.config/task-loop"
    When the config folder of "task-loop" is asked for with the plugin data folder
    Then the folder is "/plugins/data/x/config"

  Scenario: Nothing exists until it is asked for
    Given a real home folder
    When the state folder of "task-loop" is asked for
    Then the folder does not exist
    When the state folder of "task-loop" is asked for and created
    Then the folder exists

  Scenario: An app name that is not one folder is refused
    When the config folder of "a/b" is asked for
    Then the name is refused
