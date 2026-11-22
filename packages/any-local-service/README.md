# any-local-service

**Hold one local ASGI service; stop caring about browser access, health, serving and discovery.**

Default view: `LocalService(app, token=...)` is ready at once; it answers `/healthz` before the token, requires the token
header (or the cookie it sets) on every other request, refuses a foreign Host or Origin, and serves on `127.0.0.1`.
Opt-ins: `header` and `cookie` names, `version`, and a `Readiness` for staged boot; nothing else is switched on implicitly.

```python
import secrets

from any_local_service import LocalService
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


async def home(request):
    return PlainTextResponse("hello")


service = LocalService(Starlette(routes=[Route("/", home)]), token=secrets.token_urlsafe(32), version="1.0")
service.run(port=8765)
```

The value is `LocalService`: its guarded ASGI app and `readiness`. Calling the value
serves ASGI; `run()` owns the foreground server and its signals. The default view is
GET `/healthz`: readiness, stage, message, progress/files when known, and version.
Nothing reads environment variables, invokes git or creates credential files.

For an existing event loop, `async with service.serving() as url:` yields a bound,
ready-to-accept URL on an ephemeral port. `serving(endpoint=Path("service.url"))`
opts into discovery I/O: atomically write that URL after startup and unlink before
stopping the server, including when the body raises. Expensive work is injected by
the caller; no background diagnostics start implicitly.

## Rules

- Only IPv4 loopback binds; `port=0` asks the kernel. Refuse ports outside 0–65535.
- Host must be `127.0.0.1:<bound-port>` or `localhost:<bound-port>`; port 80 also
  accepts the names without a port. Origin, when present, must exactly equal
  `http://<Host>`. The boundary covers health and MCP routes too. No CORS wildcard.
- GET/HEAD `/healthz` precedes authentication. An immediately available app starts
  ready; inject `Readiness` for staged boot. Other health methods remain protected.
- HTTP requires `X-Local-Token`. A root `/?t=<token>` navigation exchanges the token
  for an HttpOnly, SameSite=strict cookie and 303 to `/`; no query token remains.
  Exchanges set no-store and no-referrer. An explicit header wins over a cookie.
  WebSockets are refused. HTTP cookies are intended solely for this loopback bind.
- Header comparison belongs to `asgi-token-gate`; lifecycle and socket ownership
  belong to `async-scope`, atomic publication to `atomic-io`. No forked primitives.
- Shutdown drains connections within a bound and runs the app's lifespan shutdown.
  Two known teardown log records are filtered for the serving lifetime; other
  errors pass. `ResponseOnceMiddleware` drops a duplicate response and tolerates an
  AnyIO closed-resource error only after the original response completed.
- A service owns its endpoint path exclusively. The caller chooses a path outside
  credential storage and prevents two services from publishing to the same path.
- All contracts are candidate. Version `0.1.0`, release tag
  `any-local-service-v0.1.0`; this change creates no tag and claims no live adoption.

## Concern modules

| Module | Responsibility |
|---|---|
| `service` | The held `LocalService` and safe default composition |
| `access` | Browser exchange and cookie-to-header adaptation |
| `boundary` | Host/Origin authority refusal |
| `health` | Public health and `ReadinessGate` boot publication |
| `readiness` | Stages, progress, refusal, listeners and live blockers |
| `serve` | Foreground uvicorn or scoped async-scope serving |
| `endpoint` | Atomic URL publication for one lifetime |
| `logs` | Scoped, precise teardown filters |
| `once` | One completed HTTP response despite a late transport close |
| `version` | Injected build identity and attach-time skew refusal |

`ReadinessGate(readiness, boot, version=..., on_failure=...)` owns the boot task.
The boot takes `publish(app)`, owns that app's lifespan, publishes once usable, and
waits until cancelled. It reports stages through `Readiness`; a failure is retained
as `gate.failure`, permanently refuses readiness and calls `on_failure`. The host
decides how to stop or raise. Compose it inside `LocalService` with the same readiness.

`build_identity(base, count=..., commit=...)` takes the consumer's build metadata;
without metadata it returns the bare version. `check_attach_version(client, server)`
raises `ServerVersionSkewError` only for a strictly newer client commit count.
Equal, older, bare or missing identities attach. Counts must describe the same
package path and append-only history: this is not SemVer or arbitrary branch ordering.

## Extraction decisions: DEEP · STABLE · WINS

Each included shape already ran in a donor. One consumer today is sufficient for
promotion; ogy can adopt now and a2kay can adopt the concern modules later.

| Donor piece | In/out and why |
|---|---|
| ogy loopback bind and port handling | In, through async-scope. Deep socket ownership and ephemeral ports; stable TCP semantics; removes repeated bind/validation glue. |
| ogy health before token | In. Middleware ordering is the safety contract; stable HTTP surface; one composition prevents accidental auth gating. |
| ogy browser cookie exchange | In. Navigation cannot set the header; stable cookie/redirect semantics; hides browser/header adaptation while reusing StaticTokenGate. |
| ogy Host/Origin protection | In. Hides DNS rebinding and cross-origin refusal rules; stable local authority boundary; covers every route including public health. |
| ogy uvicorn graceful shutdown | In. Foreground signals stay with uvicorn; scoped serving reuses async-scope with its lifespan defect fixed there. Avoids another server lifecycle implementation. |
| a2kay healthz + readiness | In. Boot task ownership, staged readiness and blockers are deeper than JSON output; donor-proven interface; replaces transport/healthz.py and transport/readiness.py. |
| a2kay teardown log filters | In, scoped to lifetime. Precise known upstream races; stable narrow message/cause matching; replaces serve.py filter classes and install functions without hiding unrelated failures. |
| a2kay response_once | In. A completed reply cannot be replaced by a late transport error; stable ASGI messages; replaces transport/response_once.py and narrows suppression to completed replies. |
| a2kay build identity/skew | Generic part in. Orderable identity and proven-newer refusal; stable pure functions; replaces formatting and skew logic in transport/version.py. Git lookup, version import, process caching and A2KAY_BUILD_* policy stay with a2kay. |
| a2kay endpoint URL file | In. Atomic publication tied to the bound server lifetime; stable path/URL shape; replaces serve_cli_endpoint's write/try/finally/unlink block. |
| a2kay loop_lag | Out. Thread/frame diagnostics and environment threshold policy do not yet win for ogy; background cost and reporting shape need a live demand. |
| ogy api.py | Out. Board inspection, HTML, refusal mapping and target loading are application behavior. No generic API router was extracted from unrelated domain routes. |
| ogy token file location | Out. Git-dir/.ogy layout is consumer storage policy; the consumer still calls stable_token. |
| ogy serve_options.py | Out. The port default and legacy export option are CLI policy; generic port validation is already in the serving boundary. |
| MCP tool construction and protocol config | Out. Consumers construct their ASGI app and own its lifespan; no FastMCP dependency or tool registration belongs here. |

## ogy adoption after coordinator release

Add the dependency and source to ogy's `pyproject.toml` after the coordinator has
published the tag (do not pin an unpublished release):

```toml
# Add to [project].dependencies:
# "any-local-service>=0.1,<1"

[tool.uv.sources]
any-local-service = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/any-local-service", tag = "any-local-service-v0.1.0" }
# Update ogy's existing async-scope source to the corrected lifecycle release:
async-scope = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/async-scope", tag = "async-scope-v0.4.1" }
```

In ogy's existing dependency list, also change `"async-scope[asgi]==0.3.0"` to
`"async-scope[asgi]==0.4.1"`. Keep its existing asgi-token-gate and atomic-io sources.
Both new tags must be published by the coordinator before resolution.

In `src/ogy/web/serve.py`, replace the `uvicorn`, `async_scope.asgi`, Request and
JSONResponse imports with `from any_local_service import LocalService`. Keep the
Starlette/Mount imports and ogy API/MCP/RefusalError wiring. Import only
`resolve_token` from `ogy.web.token`. Delete the local `LoopbackBoundary` class.
Change the application return type to `LocalService`, drop its `port` argument,
and replace its final return with:

```python
return LocalService(app, token=token, header="X-Ogy-Token", cookie="ogy_session")
```

Keep main's public signature and `resolve_token(target.repo)`. Replace its port
validation and bind/uvicorn block with:

```python
service = application(target, token)
service.run(port=port, on_bound=lambda url: sys.stderr.write(f"ogy board: {url}/?t={token}\n"))
```

Map the serving boundary's `ValueError` to ogy's `RefusalError` at its CLI edge if
that CLI requires its existing refusal type. In `src/ogy/web/token.py`, delete
`BrowserTokenGate` and its now-unused imports; keep `resolve_token` unchanged.
No ogy or a2kay files are modified by this delivery.

a2kay can replace its healthz/readiness and response-once imports with the concern
modules directly, retaining its existing boot and lifespan wiring. `ReadinessGate`
also accepts its existing `details` callback for host-specific warm-up health data;
those details cannot override readiness, stage or version. Keep that gate outside
the token-protected published app as today. Its endpoint/log/version replacements
are listed in the extraction table; the consumer still supplies build metadata.

## Verification

`uv run pytest packages/any-local-service/tests` exercises TestClient plus real
ephemeral loopback servers, with no subprocess servers. `uv run just check` is the
repository gate. See the delivery report for actual results and environment limits.
