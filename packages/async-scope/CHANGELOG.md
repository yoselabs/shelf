# async-scope — changelog

AI-facing only: one line per contract-shape change, arrow notation.

- 0.4.0: `cleanup(*steps, within) -> None` (async: every step attempted, each in its own shielded task bounded by `timeout`, TimeoutError on overrun) and `cleanup_sync(*steps) -> None`: no failure ⇒ returns, one ⇒ that exception unchanged, several ⇒ `ExceptionGroup` (`BaseExceptionGroup` with a cancel or KeyboardInterrupt, a cancel is never swallowed); BREAKING  ⇒  `ResourceScope.aclose()` collects BaseException (was Exception) and raises several failures as a group (was: first only); `to_thread_joined` raises a group `[CancelledError, failure]` when the thread failed during a cancel (was: CancelledError only); `serve_asgi` teardown no longer swallows a failing serve task or socket close
- 0.4.1: `serve_asgi` immediate forced exit  ⇒  bounded connection drain followed by the application lifespan shutdown (was: lifespan cleanup skipped)
