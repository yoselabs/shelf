# Checked exceptions for Python: can the shelf verify "a raised typed exception is handled"?

Bead shelf-tyld.22. Researched 2026-11-21 on `main` at 1633803. The scratch prototype was not committed.

## Verdict

- ❌ **Refuse the effects-style call-graph check** (a caller must catch or re-declare each typed exception). Measured: 3 cross-package hits in the whole repo, 1 true.
- ❌ **Refuse a `Result` return type**: it replaces "raise, caller catches" (ADR 0030) instead of checking it.
- ✅ **Do the narrow slice Article III already owes**: a planted-violation test for swallowed exceptions. The "No silent failures" row of the Article III table is still `task`.
- Revisit the call-graph check when cross-package calls to typed raisers pass ~50 (now 13), or more than one package adopts a2effect `Raises`.

## 1. What a2effect is here

- `AppError` base (kind, code, http status, envelope) and `Annotated[T, Raises(A, B)]` on a tool's return type.
- Three AST lint rules (`python -m a2effect.lint`): `RAISES-CLOSURE` (a `raise X` in a tool body must be declared), `RAISES-UNCOVERED` (a registry-known throwing call such as httpx, neither declared nor in a `try`), `RAISES-NOT-TYPED`.
- **Scope: one function body, tools only.** It never checks that a caller of a tool handles the declared set: the declaration half of an effect system without the caller half. Its README also refuses a Result monad.
- Adoption: one other package mentions it (`mcp-arg-errors/wire.py`, in prose). The shelf's own typed exceptions (`NotAWorktree`, `GitUnavailable`, `IndexLocked`) are plain classes, not `AppError`.

## 2. Mechanisms (each run, not guessed)

| Mechanism | Result | Verdict |
|---|---|---|
| pyrefly 1.3.2 | A callee raising `NotAWorktree`, a caller calling it bare: `0 errors`. No raises analysis exists. | ❌ cannot |
| ruff `DOC501` / `DOC502` (preview) | Flags a `raise X` missing from the docstring, and a documented exception never raised, **inside the callee only**. | ⚠️ half; not enabled (`D` is absent on purpose) |
| ruff `BLE`, `TRY`, `B904` | Already selected; `except Exception: pass` is flagged. `PLW0706` does not exist (unknown selector). | ✅ already here |
| `Raises:` docstrings + AST pass | 6 `Raises:` sections in 88 packages. Prose like "Raises X ..." is missed by any parser. | ⚠️ no convention yet |
| `Result` (returns-style) | Not run. Every call site unwraps; contradicts ADR 0030 and Article III. | ❌ |
| Call-graph AST pass | Prototyped, below. | ❌ at this scale |

## 3. Measurement (scratch pass, `packages/*/src`, 421 files, 1.1 s)

Rule: the callee raises a shelf-defined exception directly or documents it; a call from another module has no enclosing `except` covering it (MRO-aware) and no `Raises:` re-declaration.

- Module-level functions 1,683, public 942. Public functions raising a shelf typed exception directly: **71**. With a `Raises:` section or `Raises(...)`: **3**. Public methods 827, 67 of them raising (not resolvable, see limits). Shelf exception classes: 87.
- Calls 10,523; statically resolved to a shelf function: **2,315 (22%)**.
- **Cross-package** call sites to a public typed raiser: 13 direct, 15 transitive. Unhandled and undeclared: **1 direct, 3 transitive**.
- Judged by reading the code, all 3. `any_agent.procs.spawn` leaks `RegisteredStartUncertainError`, undocumented: **true**. `any_speech.defaults.find_fluidaudio` handles `NotFound` with `contextlib.suppress`, which the pass does not read: **false (tool gap)**. `any_yaml.write.merge3_text` documents `MergeConflictError` in prose, not a `Raises:` section: **false (convention gap)**. **False-positive rate 2/3 = 67%**, n=3.
- Wide mode (any other module, same package included): 108 call sites, **90 unhandled**. A random 15 (all git-porcelain: `checkout` -> `require_index` -> `IndexLocked`, `rebase_onto` -> `GitUnavailable`, ...) are true by the rule, and every one is a public verb deliberately passing the package's own typed error through. Acting on them means about 90 re-declarations: the signature-propagation cost of Java checked exceptions, with no handler added. I judged these from the call pattern, not by reading all 15 bodies.

**Hard limits:**
- Method calls on instances, protocols and injected collaborators (Article II style, git-porcelain's real/fake pair) are unresolvable.
- Stdlib and third-party raises are invisible unless hand-registered (a2effect's registry approach).
- `with suppress(...)`, `except*`, and a handler that re-raises a different type each need extra code.
- Bare re-raise and `raise var` are skipped; classes of the same name in two packages merge.
- Article III already bans `except Exception` swallowing through BLE; the gap is narrower swallows (`except OSError: pass`).

## 4. Decision under Article VII

Extract only what real code shows. Real code shows 13 cross-package calls to typed raisers and one real leak. The mechanism is a walker with 22% call resolution and a 67% false-positive rate on the only measured sample. Cost for AI authors: every public raiser carries a `Raises:` line and every propagating caller repeats it. That grows each docstring, which the owner counts as API size, to catch about one bug.

The cheaper substitute already holds: the error is a named class, so `grep NotAWorktree` finds every handler (ADR 0030's argument).

**Recommended first slice:** `tests/test_arch_swallowed_exceptions.py`, swallowed handlers only; no a2effect needed.

## 5. Arch-test sketch (planted violations)

Follows `tests/test_arch_threads.py`: scanner, allowlist rows with reasons, stale-row check, scanner self-test.

```python
def swallowed(source: str) -> list[int]:
    """Line of each `except` whose body only passes/continues/returns None, and each `with suppress(...)`,
    unless the handler re-raises or logs."""

_ALLOWED = {  # file -> reason
    "packages/x/src/x/y.py": "cleanup after the stop already happened; the caller logs the failure",
}

def test_no_swallowed_exception_outside_listed_files(): ...   # scan packages/*/src, fail on unlisted
def test_every_listed_file_still_swallows(): ...              # stale row: a listed file with no hit
def test_every_listed_file_has_a_reason(): ...                # reason non-empty
@pytest.mark.parametrize(("source", "count"), [               # planted
    ("try:\n    f()\nexcept OSError:\n    pass\n", 1),
    ("with contextlib.suppress(KeyError):\n    f()\n", 1),
    ("try:\n    f()\nexcept OSError:\n    raise\n", 0),
    ("try:\n    f()\nexcept OSError as e:\n    log.warning('x', exc_info=e)\n", 0),
])
def test_the_scanner_sees_what_it_claims_to(source, count): ...
```

Not measured: the allowlist size this would need. Today `src` has 32 `contextlib.suppress` and 48 `except Exception` sites; the count of reasoned rows is the real cost.
