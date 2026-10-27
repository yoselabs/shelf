Feature: Spans, waits and counts read the same everywhere

  Scenario Outline: A span is shown in days, hours and minutes
    When the span of <seconds> seconds is formatted
    Then it reads "<text>"

    Examples:
      | seconds | text  |
      | 0       | 0m    |
      | -90     | 0m    |
      | 59      | 0m    |
      | 720     | 12m   |
      | 11220   | 3h07m |
      | 86400   | 1d0h  |
      | 191000  | 2d5h  |

  Scenario: A wait toward a moment ahead reads as a span
    Given the clock reads 1000 seconds
    When the wait until 8200 seconds is formatted
    Then it reads "2h00m"

  Scenario: A moment that has passed is now
    Given the clock reads 1000 seconds
    When the wait until 400 seconds is formatted
    Then it reads "now"

  Scenario Outline: A count is shown by magnitude
    When the count <n> is formatted
    Then it reads "<text>"

    Examples:
      | n       | text  |
      | 0       | 0     |
      | 950     | 950   |
      | 12400   | 12k   |
      | 999999  | 1.0M  |
      | 1500000 | 1.5M  |
      | -2500000 | -2.5M |
