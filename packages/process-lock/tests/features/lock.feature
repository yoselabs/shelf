Feature: One holder owns a path, and waiters can wait, give up or break a dead holder

  Scenario: A waiter gets the lock when the holder lets go within the timeout
    Given a lock on "a.lock" held by another thread for 0.3 seconds
    When I acquire "a.lock" waiting up to 5 seconds
    Then I hold "a.lock"
    And the waiting callback was called with the holder's pid

  Scenario: A waiter gives up at the timeout
    Given a lock on "a.lock" held by another thread for 5 seconds
    When I acquire "a.lock" waiting up to 0.3 seconds
    Then the acquire is refused naming the holder's pid
    And the waiting callback was called with the holder's pid

  Scenario: The holder record is readable without the lock
    Given I hold "a.lock" with label "sync" and meta {"job": 7}
    Then holder "a.lock" shows my pid, label "sync" and meta {"job": 7}

  Scenario: A recorded holder that is gone does not unlock a held lock
    Given a lock on "a.lock" whose record names a dead process
    When I acquire "a.lock" waiting up to 0.2 seconds
    Then the acquire is refused saying the descriptor is inherited and the recorded pid is gone

  Scenario: Non-reentrant mode refuses a second acquire in the same process
    Given I hold "a.lock" non-reentrantly
    When I acquire "a.lock" waiting up to 0.2 seconds
    Then the acquire is refused naming my pid

  Scenario: Non-reentrant mode waits for the first handle to be released
    Given I hold "a.lock" non-reentrantly
    And I release it after 0.3 seconds
    When I acquire "a.lock" non-reentrantly waiting up to 5 seconds
    Then I hold "a.lock"
