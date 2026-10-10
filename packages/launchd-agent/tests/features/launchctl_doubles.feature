Feature: launchctl doubles keep a test away from the user's launchd

  Scenario: The fake round-trips an install
    Given a fake launchctl
    When an agent "dev.example.agent" is installed, checked and uninstalled
    Then the status after install is installed and loaded
    And the status after uninstall is neither
    And the fake saw "bootstrap, print, bootout, print"

  Scenario: The refusing fake fails a bootstrap the way launchd does
    Given a fake launchctl that refuses bootstrap
    When an agent "dev.example.agent" is installed
    Then the install fails naming "5"
    And no plist is left behind

  Scenario: A launchctl on the path that refuses everything
    Given a folder with the refusing launchctl first on the path
    When "launchctl print gui/501" runs by name
    Then it exits 1 saying "launchctl is not available to tests"
