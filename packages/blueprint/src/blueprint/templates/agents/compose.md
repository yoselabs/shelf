# Compose conventions

Stack: compose (Docker Compose files). The gate is `just check`; this file is what to know before changing a compose file.

## Tools per role

| role | tool | configured in |
|---|---|---|
| types | `docker compose -f <file> config --no-interpolate -q` per file: Docker's own schema check, no daemon, no env needed | the gate recipe |
| linter | dclint `--max-warnings 0` (its default exit is 0 on warnings) | `.dclintrc`, each disabled rule with a reason |
| dependencies | every `image:` is `name:tag@sha256:<digest>`: the tag for people, the digest for the machine | the gate recipe |
| spelling | typos with a committed config | `typos.toml` |
| hooks | prek: config check, dclint and the digest check on staged compose files | [gate.md](gate.md) |

Dockerfiles beside the compose files are linted by hadolint (the dockerfile stack's row), not here.

## Rules

| rule | why |
|---|---|
| Pin each image by tag and digest; bump with the repo's updater, then re-run `just check` | A tag moves; a digest is the image you tested |
| Never paste a secret into a compose file: reference `${VAR:?}` and keep the value in the sealed env file | The file is in git; `:?` fails fast when the value is missing |
| No `privileged: true`, host network or `docker.sock` mount without a comment saying why | Each gives the container the host |
| Publish a port on an explicit interface (`127.0.0.1:8080:80`), not bare | A bare port listens on every interface |
| A rendered or generated compose file is edited at its source | The next render overwrites a hand edit |
| Remove the obsolete top-level `version:` key | Compose v2+ ignores it and warns |

## Run

```bash
just check    # the gate: config check, dclint, digest pins
```
