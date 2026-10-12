package main

import rego.v1

test_privileged_denied if {
	count(deny) == 1 with input as {"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"]}}, "networks": {"n": {}}}
}

test_clean_passes if {
	count(deny) == 0 with input as {"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "networks": ["n"], "ports": ["127.0.0.1:80:80"]}}, "networks": {"n": {}}}
}

test_exempt_needs_reason if {
	count(deny) == 1 with input as {"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "privileged": true, "networks": ["n"], "x-policy-exempt": {"privileged": " "}}}, "networks": {"n": {}}}
}

test_undeclared_network_denied if {
	count(deny) == 1 with input as {"services": {"a": {"healthcheck": {"test": ["CMD", "true"]}, "networks": ["ghost"]}}}
}

test_missing_healthcheck_denied if {
	count(deny) == 1 with input as {"services": {"a": {"networks": ["n"]}}, "networks": {"n": {}}}
}
