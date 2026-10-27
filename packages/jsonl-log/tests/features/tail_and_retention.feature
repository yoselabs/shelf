Feature: A log that several processes write and a reader follows by byte cursor

  Scenario: A reader resumes from its cursor and a torn last line waits
    Given a log holding the lines {"n": 1} and {"n": 2}
    When a reader reads from the start
    Then it gets the lines 1 and 2
    When a writer has written {"n": 3} only up to its half
    And the reader reads from its cursor
    Then it gets no lines
    When the writer finishes the line
    And the reader reads from its cursor
    Then it gets the lines 3

  Scenario: A line that is not an object is skipped and the cursor passes it
    Given a log holding the raw lines "[1, 2]", "not json" and {"n": 9}
    When a reader reads from the start
    Then it gets the lines 9

  Scenario: Appends report where the line starts
    Given a log holding the lines {"n": 1} and {"n": 2}
    When {"n": 3} is appended
    Then the reported offset is the size the log had before
    And the last 2 lines are 2 and 3

  Scenario: Four processes append at once and no line is torn
    Given an empty log
    When 4 processes each append 50 long lines
    Then the log holds 200 whole lines

  Scenario: Rotated files nobody wrote to for a week are deleted
    Given a rotating log with two rotated files, one written 8 days ago and one 1 day ago
    When the log is pruned with a limit of 7 days
    Then only the file written 1 day ago is left
