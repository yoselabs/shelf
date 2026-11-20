# compose gaps: formatter, architecture, tests (shelf blueprint, 2026-10-11)

Evidence key: T = run here (exit code given); R = read in a file; U = untested. Machine: no docker CLI, no daemon (T: `which docker` empty).
Tools via `mise exec`: conftest 0.71.1 (OPA 1.21.1), yamlfmt 0.21.0; npx prettier 3.6.2. Scratch clone of homelab main (42 compose files: 19 stacks/*, 20 hosts/*/rendered, 3 other).
Files here: roles.toml (the three role blocks), policy/compose.rego + compose_health.rego + compose_test.rego, plant/*.yml, bundle_modes_test.py, fm.sh, cmp.sh.

## architecture: standard = conftest policy, alternative = tools/stack_policy.py
| rule | conftest (policy/compose.rego) | homelab stack_policy.py + homelab_stack.deny_hits |
|---|---|---|
| privileged | T red on plant (exit 1), 2 real hits | R+T enforced: deny_hits on plant -> privileged |
| network_mode: host | T red; 10 real hits | R+T enforced (host_network); also pid: host, cap_add, devices, host_path |
| docker.sock mount | T red (short+long syntax); 5 real | R+T enforced (docker_socket) |
| unbound published port | T red (short+long); 4 real (traefik 80, 3 UDP game ports) | NOT enforced (R: no ports rule; only dclint, disabled in .dclintrc) |
| every service on a declared network | T red (ghost net, no key); 13 real "no networks:" | NOT enforced |
- Exemptions: conftest = `x-policy-exempt: {rule: "reason"}` in the service (blank reason ignored; T: exempted 7th plant service passes). stack_policy = dated `[[stack.exempt]]` in stack.toml (R).
- conftest reads YAML directly, no `compose config` needed (T). Limit: file as written, no `${VAR}` or override-merge resolution.
- Runs: good plant exit 0; bad plant 6 deny, exit 1; `conftest verify` 5 rego tests pass; 20 real rendered files: 34 architecture findings (T, exit 1) = what homelab's allow entries accept today.
- stack_policy.py itself U: it shells out to `docker compose config` (no CLI here); only its pure function deny_hits was run (T, via python).

## formatter: yamlfmt provisional standard; generated compose na
| fact | evidence |
|---|---|
| planted badly indented file: yamlfmt -lint exit 1, after fix exit 0; prettier --check exit 1, after --write exit 0 | T |
| homelab stacks/*/compose.yml not clean: yamlfmt 14/19, prettier 14/19 | T |
| rendered not clean: 20/20 both | T |
| comments kept (count equal on all 19) by both; hand-aligned trailing comments re-spaced to one space by both | T (diff on hermes) |
| prettier also rewrites flow lists to block (201 diff lines vs 116) | T |
| yamlfmt with `retain_line_breaks_single`: 11/19 dirty, 83 diff lines | T |
- Verdict: yamlfmt (one opinion, keeps comments) as the role; rendered compose is formatted by tools/render.py, not by a formatter. Not `na`: nothing mangles comments. Homelab adoption = one reformat of deploy inputs (redeploys); that is homelab's call.

## tests: static substitutes, partly standard
| check | evidence |
|---|---|
| healthcheck on every service (compose_health.rego) | T red on plant (exit 1); 8 real services lack one (cadvisor, vector x2, openobserve, keys, qbittorrent-mcp, oauth2-proxy) |
| bundle keeps file modes (incident 3ac475a, 2026-10-01) | R: the fix commit changed only tools/stack_bundle.py, no test |
| homelab existing tests vs planted mode-644 start script | T: test_ci_deploy + test_homelab_stack, 44 passed both before and after the plant: they do NOT see the incident |
| new test bundle_modes_test.py (sb.build + `tar mode & 0o111`) | T red exit 1 on 644, green at 755 |
| `docker compose up --wait` + probe | U: needs a daemon and sealed secrets; 7675580 health layer is R only |
- Verdict: tests = healthcheck policy + a bundle pytest, both seen red. Real smoke stays U (missing evidence: a Docker daemon and one stack that boots without secrets; homelab's tools/deploy-smoke stack is the candidate).

## Remaining
Not run: stack_policy.py end to end; conftest on `compose config` JSON (merged/interpolated); recipe wiring in __main__.py (RECIPE_FILES) and a detection test for the new `config` clauses.
