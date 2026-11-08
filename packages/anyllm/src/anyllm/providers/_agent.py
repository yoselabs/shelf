"""Project a supervised agent run into the completion contract."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from anyllm.base import Completion
from anyllm.errors import AnyLLMError

if TYPE_CHECKING:
    import types

    from any_agent import Harness, LaunchSpec


async def complete_run(agent: types.ModuleType, harness: Harness, spec: LaunchSpec, model: str) -> Completion:
    """Run the synchronous supervisor off the event loop; CLI errors never permit API fallback."""
    t0 = time.perf_counter()
    try:
        result = await asyncio.to_thread(agent.run, harness, spec, 0)
    except OSError as exc:
        msg = f"failed to invoke {harness.kind} CLI: {exc}"
        raise AnyLLMError(msg, retryable=False) from exc
    summary = result.summary
    outcome = agent.classify(
        summary.rc,
        summary.vendor,
        summary.stderr,
        result.timed_out,
        summary.work,
        structured=summary.facts,
    )
    if outcome is not None or summary.rc != 0 or result.rc != 0 or result.stop not in (None, "answer"):
        detail = outcome.detail if outcome else summary.stderr or str(result.stop or "run failed")
        msg = f"{harness.kind} CLI exited {result.rc}: {detail[:300]}"
        raise AnyLLMError(
            msg,
            retryable=False,
            hint=f"check `{harness.kind}` auth / subscription credit; this adapter never falls back to the billed API",
        )
    if not summary.text:
        msg = f"{harness.kind} CLI returned no completion"
        raise AnyLLMError(msg, retryable=False)
    tokens = summary.res.get("tokens") or {}
    return Completion(
        text=summary.text,
        model=model,
        prompt_tokens=int(tokens.get("in") or 0),
        completion_tokens=int(tokens.get("out") or 0),
        cost_usd=summary.cost,
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )
