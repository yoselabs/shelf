# Compose policy (blueprint recipe `compose-policy`): architecture (five deny rules) and the healthcheck rule tests read. conftest reads the compose YAML directly,
# no Docker CLI needed:
#   conftest test --combine --policy policy docs/blueprint/blueprint.toml $(git ls-files 'compose.y*ml')
# --combine hands the policy every file at once as input[i] = {path, contents}. docs/blueprint/blueprint.toml is one of
# them: its [[override]] tables are the exemptions, the same file and format every blueprint exception uses. (conftest
# 0.71.1 loads only .json and .yaml through --data, so the TOML cannot arrive as data.override; as an input it parses.)
# A service is excused from one rule by an override with a reason:
#   [[override]]
#   id = "compose.privileged"          # compose.<rule>: privileged, host_network, docker_socket, unbound_port, default_network, healthcheck
#   scope = "service:cadvisor"
#   reason = "reads host counters"
#   decided_by = "owner"
#   expires = 2027-04-01               # or adr = "NNNN"
# An override past its `expires` excuses nothing. The old `x-policy-exempt` key is not read; it is denied, with the move.
package main

import rego.v1

is_blueprint(f) if endswith(f.path, "blueprint.toml")

compose_files := [f | some f in input; not is_blueprint(f)]

overrides := [o | some f in input; is_blueprint(f); some o in f.contents.override]

# every (file, service name) pair
services contains [f.path, name] if {
	some f in compose_files
	some name, _ in f.contents.services
}

svc(path, name) := f.contents.services[name] if {
	some f in compose_files
	f.path == path
}

declared(path, net) if {
	some f in compose_files
	f.path == path
	f.contents.networks[net]
}

exempt(name, rule) if {
	some o in overrides
	o.id == concat(".", ["compose", rule])
	o.scope == concat(":", ["service", name])
	reasoned(o.reason)
	not lapsed(o)
}

reasoned(reason) if {
	is_string(reason)
	trim_space(reason) != ""
}

# toml dates arrive as "2027-04-01" or "2027-04-01T00:00:00Z"; no expiry (an adr) never lapses
lapsed(o) if {
	is_string(o.expires)
	time.parse_ns("2006-01-02", substring(o.expires, 0, 10)) < time.now_ns()
}

deny contains msg if {
	not is_array(input)
	msg := "conftest ran without --combine: the policy reads docs/blueprint/blueprint.toml beside the compose files; run `conftest test --combine --policy policy docs/blueprint/blueprint.toml <compose files>`"
}

deny contains msg if {
	some [path, name] in services
	svc(path, name).privileged == true
	not exempt(name, "privileged")
	msg := sprintf("%s: service %q: privileged: true gives the container the host; remove it or add an [[override]] id = \"compose.privileged\" scope = \"service:%s\" with a reason to docs/blueprint/blueprint.toml", [path, name, name])
}

deny contains msg if {
	some [path, name] in services
	svc(path, name).network_mode == "host"
	not exempt(name, "host_network")
	msg := sprintf("%s: service %q: network_mode: host bypasses the network model; use a declared network or add an [[override]] id = \"compose.host_network\" scope = \"service:%s\" to docs/blueprint/blueprint.toml", [path, name, name])
}

deny contains msg if {
	some [path, name] in services
	some v in svc(path, name).volumes
	src := bind_source(v)
	contains(src, "docker.sock")
	not exempt(name, "docker_socket")
	msg := sprintf("%s: service %q: mounts the docker socket (%s), which is root on the host; if intended add an [[override]] id = \"compose.docker_socket\" scope = \"service:%s\" with a reason to docs/blueprint/blueprint.toml", [path, name, src, name])
}

bind_source(v) := split(v, ":")[0] if is_string(v)

bind_source(v) := v.source if {
	is_object(v)
	v.type == "bind"
}

deny contains msg if {
	some [path, name] in services
	some p in svc(path, name).ports
	published(p)
	not bound(p)
	not exempt(name, "unbound_port")
	msg := sprintf("%s: service %q: port %v is published on every interface; bind it (127.0.0.1:... or a host address) or add an [[override]] id = \"compose.unbound_port\" scope = \"service:%s\" to docs/blueprint/blueprint.toml", [path, name, p, name])
}

# short form: "[ip:]published:target[/proto]" (an IPv6 literal is bracketed); a bare container port is not published
published(p) if {
	is_string(p)
	count(split(p, ":")) > 1
}

published(p) if {
	is_object(p)
	p.published
}

bound(p) if {
	is_string(p)
	parts := split(p, ":")
	count(parts) >= 3
}

bound(p) if {
	is_object(p)
	p.host_ip
}

# every service sits on a network the file declares, or says network_mode
deny contains msg if {
	some [path, name] in services
	not svc(path, name).network_mode
	not svc(path, name).networks
	not exempt(name, "default_network")
	msg := sprintf("%s: service %q: no networks: key, so it lands on the project default network; list a declared network or add an [[override]] id = \"compose.default_network\" scope = \"service:%s\" to docs/blueprint/blueprint.toml", [path, name, name])
}

deny contains msg if {
	some [path, name] in services
	some net in net_names(svc(path, name))
	net != "default"
	not declared(path, net)
	msg := sprintf("%s: service %q: network %q is not declared under top-level networks:", [path, name, net])
}

# networks: is a list of names or a map name -> options
net_names(s) := {n | some n in s.networks} if is_array(s.networks)

net_names(s) := {n | some n, _ in s.networks} if is_object(s.networks)

# Every service has a healthcheck, because the deploy waits on health (a crash loop is only seen through it).
# Excuse one with an override `compose.healthcheck`; a service whose image defines HEALTHCHECK needs this too,
# since the file alone cannot show it.
deny contains msg if {
	some [path, name] in services
	s := svc(path, name)
	not s.healthcheck
	not exempt_health(name, s)
	msg := sprintf("%s: service %q: no healthcheck: the deploy cannot wait for it; add one or an [[override]] id = \"compose.healthcheck\" scope = \"service:%s\" with a reason to docs/blueprint/blueprint.toml", [path, name, name])
}

exempt_health(name, _) if exempt(name, "healthcheck")

exempt_health(_, s) if s.healthcheck.disable == true

# x-policy-exempt (the old per-service and top-level exemption) is not read any more: one override format, one file.
deny contains msg if {
	some [path, name] in services
	some rule, _ in svc(path, name)["x-policy-exempt"]
	msg := moved(path, name, rule)
}

deny contains msg if {
	some f in compose_files
	some name, rules in f.contents["x-policy-exempt"]
	is_object(rules)
	some rule, _ in rules
	msg := moved(f.path, name, rule)
}

moved(path, name, rule) := sprintf("%s: service %q: x-policy-exempt is not read any more and excuses nothing; move it to docs/blueprint/blueprint.toml: [[override]] id = \"compose.%s\" scope = \"service:%s\" reason = \"...\" decided_by = \"owner\" expires = <date> (or adr = \"NNNN\")", [path, name, rule, name])
