Feature: Match the keys a step names and nothing else

  Scenario Outline: A subset match
    Given the value:
      """
      {"title": "Harbor migration", "meta": {"version": "v1", "kind": "project"}, "tags": ["ops", "infra"], "items": [{"ref": "a/1", "n": 1}, {"ref": "b/2", "n": 2}]}
      """
    Then the value <does> match:
      """
      <expected>
      """

    Examples:
      | does     | expected                                      |
      | does     | {"title": "Harbor migration"}                 |
      | does     | {"meta": {"kind": "project"}}                 |
      | does     | {"tags": ["infra", "ops"]}                    |
      | does not | {"tags": ["ops"]}                             |
      | does     | {"items": [{"ref": "b/2"}]}                   |
      | does     | {"items": [{"ref": "b/2"}, {"n": 1}]}         |
      | does not | {"items": [{"ref": "c/3"}]}                   |
      | does not | {"meta": {"kind": "note"}}                    |
      | does not | {"owner": "the ops team"}                     |
      | does not | {"title": ["Harbor migration"]}               |
      | does not | {"meta": "v1"}                                |
      | does     | {}                                            |
