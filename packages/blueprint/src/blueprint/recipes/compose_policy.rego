# Compose policy (blueprint recipe `compose-policy`): architecture (five deny rules) and the healthcheck rule tests read. conftest reads the compose YAML directly,
# no Docker CLI needed: `conftest test --policy policy compose.yml [more files]`.
# A service is excused from one rule by a reason: in its own config, `x-policy-exempt: {privileged: "why"}`, or in a
# top-level block, `x-policy-exempt: {<service>: {privileged: "why"}}`. The top-level form sits outside the service
# config compose hashes, so recording an exemption recreates no container (homelab 2026-10: a rendered key on every
# service would have redeployed 19 placements, the devbox among them).
package main

import rego.v1

services contains name if some name, _ in input.services

svc(name) := input.services[name]

exempt(name, rule) if reasoned(svc(name)["x-policy-exempt"][rule])

exempt(name, rule) if reasoned(input["x-policy-exempt"][name][rule])

reasoned(reason) if {
	is_string(reason)
	trim_space(reason) != ""
}

deny contains msg if {
	some name in services
	svc(name).privileged == true
	not exempt(name, "privileged")
	msg := sprintf("service %q: privileged: true gives the container the host; remove it or add x-policy-exempt.privileged with a reason", [name])
}

deny contains msg if {
	some name in services
	svc(name).network_mode == "host"
	not exempt(name, "host_network")
	msg := sprintf("service %q: network_mode: host bypasses the network model; use a declared network or add x-policy-exempt.host_network", [name])
}

deny contains msg if {
	some name in services
	some v in svc(name).volumes
	src := bind_source(v)
	contains(src, "docker.sock")
	not exempt(name, "docker_socket")
	msg := sprintf("service %q: mounts the docker socket (%s), which is root on the host; add x-policy-exempt.docker_socket with a reason if intended", [name, src])
}

bind_source(v) := split(v, ":")[0] if is_string(v)

bind_source(v) := v.source if {
	is_object(v)
	v.type == "bind"
}

deny contains msg if {
	some name in services
	some p in svc(name).ports
	published(p)
	not bound(p)
	not exempt(name, "unbound_port")
	msg := sprintf("service %q: port %v is published on every interface; bind it (127.0.0.1:... or a host address) or add x-policy-exempt.unbound_port", [name, p])
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
	some name in services
	not svc(name).network_mode
	not svc(name).networks
	not exempt(name, "default_network")
	msg := sprintf("service %q: no networks: key, so it lands on the project default network; list a declared network or add x-policy-exempt.default_network", [name])
}

deny contains msg if {
	some name in services
	some net in net_names(svc(name))
	net != "default"
	not input.networks[net]
	msg := sprintf("service %q: network %q is not declared under top-level networks:", [name, net])
}

# networks: is a list of names or a map name -> options
net_names(s) := {n | some n in s.networks} if is_array(s.networks)

net_names(s) := {n | some n, _ in s.networks} if is_object(s.networks)

# Every service has a healthcheck, because the deploy waits on health (a crash loop is only seen through it).
# Excuse one with `x-policy-exempt: {healthcheck: "why"}`; a service whose image defines HEALTHCHECK needs this too,
# since the file alone cannot show it.


deny contains msg if {
	some name, s in input.services
	not s.healthcheck
	not exempt_health(name, s)
	msg := sprintf("service %q: no healthcheck: the deploy cannot wait for it; add one or x-policy-exempt.healthcheck with a reason", [name])
}

exempt_health(name, _) if exempt(name, "healthcheck")

exempt_health(_, s) if s.healthcheck.disable == true
