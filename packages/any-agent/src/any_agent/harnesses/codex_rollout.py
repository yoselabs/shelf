"""What Codex's rollout file knows that `codex exec --json` does not say: one `token_count` record per model request, with the thread's
running total. `exec --json` only reports the whole turn at its end, so a killed or timed-out run loses its usage there and a run's
request count cannot be read from the stream. The rollout (`$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<time>-<thread id>.jsonl`) has both."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from any_agent._json import Json, num, obj

KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


@dataclass(frozen=True)
class RolloutUsage:
    """`requests`: model requests in this invocation (records of a new running total at or after `since`); `total`: the thread's running
    total after the last of them (the whole thread's, resumed history included); `before`: the total when the invocation began."""

    requests: int
    total: dict[str, int]
    before: dict[str, int]

    def tokens(self) -> dict[str, Json]:
        """The thread's running total in the shape of `Summary.res["tokens"]` (input, cached, output)."""
        return {"in": self.total["input_tokens"], "cached": self.total["cached_input_tokens"], "out": self.total["output_tokens"]}


def find(sessions: Path, ref: str) -> Path | None:
    if not ref:
        return None
    return next(iter(sorted(sessions.rglob(f"*{ref}.jsonl"))), None)


def _when(raw: Json) -> float:
    try:
        return datetime.fromisoformat(str(raw)).timestamp()
    except ValueError:
        return 0.0


def read(sessions: Path, ref: str, since: float = 0.0) -> RolloutUsage | None:
    """The usage of thread `ref` from `since` (epoch seconds; 0 = the thread's start), or None when there is no readable rollout."""
    path = find(sessions, ref)
    if path is None:
        return None
    zero = dict.fromkeys(KEYS, 0)
    before, total, requests = dict(zero), dict(zero), 0
    try:
        with path.open(encoding="utf-8", errors="replace") as f:  # lossy-ok: parse: token counts from JSON lines, bad lines skipped
            for line in f:
                try:
                    raw = json.loads(line)
                except ValueError:
                    continue
                rec = obj(obj(raw).get("payload"))
                if rec.get("type") != "token_count":
                    continue
                running = obj(obj(rec.get("info")).get("total_token_usage"))
                if not running:
                    continue  # a rate-limit update carries no usage
                now = {k: int(num(running.get(k))) for k in KEYS}
                if now == total:
                    continue  # the same running total again: the same request
                if _when(obj(raw).get("timestamp")) < since:
                    before = now
                else:
                    requests += 1
                total = now
    except OSError:
        return None
    return RolloutUsage(requests=requests, total=total, before=before)
