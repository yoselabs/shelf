package main

import rego.v1

# conftest --combine: every file at once, the compose file beside docs/blueprint/blueprint.toml with its [[override]] tables.
files(compose, overrides) := [
	{"path": "compose.yml", "contents": compose},
	{"path": "docs/blueprint/blueprint.toml", "contents": {"override": overrides}},
]

test_privileged_denied if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [])
}

test_clean_passes if {
	count(deny) == 0 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "networks": ["n"], "ports": ["127.0.0.1:80:80"]}}, "networks": {"n": {}}}, [])
}

test_override_needs_a_reason if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [{"id": "compose.privileged", "scope": "service:a", "reason": " "}])
}

# The exemption is an [[override]] table of docs/blueprint/blueprint.toml.
test_override_excuses_the_named_service if {
	count(deny) == 0 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [{"id": "compose.privileged", "scope": "service:a", "reason": "the GPU needs it"}])
}

test_override_excuses_only_its_service if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}, "b": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [{"id": "compose.privileged", "scope": "service:a", "reason": "the GPU needs it"}])
}

test_override_excuses_only_its_rule if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "network_mode": "host"}}}, [{"id": "compose.privileged", "scope": "service:a", "reason": "the GPU needs it"}])
}

test_override_without_a_service_scope_excuses_nothing if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [{"id": "compose.privileged", "reason": "the GPU needs it"}])
}

test_override_covers_the_healthcheck if {
	count(deny) == 0 with input as files({"services": {"a": {"networks": ["n"]}}, "networks": {"n": {}}}, [{"id": "compose.healthcheck", "scope": "service:a", "reason": "the image defines HEALTHCHECK"}])
}

test_no_override_means_no_exemption if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [])
}

# x-policy-exempt is no longer read: it is denied, with the move.
test_service_x_policy_exempt_is_denied_with_the_move if {
	msgs := deny with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "networks": ["n"], "x-policy-exempt": {"privileged": "why"}}}, "networks": {"n": {}}}, [])
	count(msgs) == 1
	some m in msgs
	contains(m, "x-policy-exempt")
	contains(m, "[[override]]")
	contains(m, "compose.privileged")
	contains(m, "service:a")
}

test_x_policy_exempt_no_longer_excuses if {
	count(deny) == 2 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"], "x-policy-exempt": {"privileged": "why"}}}, "networks": {"n": {}}}, [])
}

test_top_level_x_policy_exempt_is_denied_with_the_move if {
	msgs := deny with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "networks": ["n"]}}, "networks": {"n": {}}, "x-policy-exempt": {"a": {"healthcheck": "why"}}}, [])
	count(msgs) == 1
	some m in msgs
	contains(m, "compose.healthcheck")
	contains(m, "service:a")
}

test_undeclared_network_denied if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "networks": ["ghost"]}}}, [])
}

test_missing_healthcheck_denied if {
	count(deny) == 1 with input as files({"services": {"a": {"networks": ["n"]}}, "networks": {"n": {}}}, [])
}

test_without_combine_the_policy_says_so if {
	msgs := deny with input as {"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "networks": ["n"]}}, "networks": {"n": {}}}
	count(msgs) == 1
	some m in msgs
	contains(m, "--combine")
}

test_an_expired_override_excuses_nothing if {
	count(deny) == 1 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [{"id": "compose.privileged", "scope": "service:a", "reason": "r", "expires": "2020-01-01T00:00:00Z"}])
}

test_a_live_override_excuses if {
	count(deny) == 0 with input as files({"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}, [{"id": "compose.privileged", "scope": "service:a", "reason": "r", "expires": "2099-01-01T00:00:00Z"}])
}
