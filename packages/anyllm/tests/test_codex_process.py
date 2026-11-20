"""The codex-cli adapter against a fake `codex` executable on PATH: a real child process, no model, no network."""

import asyncio
import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from anyllm import (
    AnthropicApiAdapter,
    ClaudeCodeCliAdapter,
    ClaudeCodeSdkAdapter,
    CodexCliAdapter,
    OpenAICompatibleAdapter,
    require_structured,
)
from anyllm.errors import AnyLLMError

SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"], "additionalProperties": False}

# The fake: records what it was given, then answers like `codex exec --json -o F -`, or hangs (a `.hang` file beside the record).
FAKE = f"""#!{sys.executable}
import json, os, sys, time
RECORD = "@RECORD@"  # the child gets an allow list, so the path is baked in, not passed in the environment
argv = sys.argv[1:]
record = {{
    "argv": argv, "cwd": os.getcwd(), "cwd_files": os.listdir("."), "stdin": sys.stdin.read(),
    "env": {{k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "KEEP_ME")}}, "pid": os.getpid(),
    "schema": open(argv[argv.index("--output-schema") + 1]).read() if "--output-schema" in argv else None,
}}
open(RECORD + ".part", "w").write(json.dumps(record))
os.rename(RECORD + ".part", RECORD)  # atomic: the test waits on the name
print(json.dumps({{"type": "thread.started", "thread_id": "t1"}}), flush=True)
if os.path.exists(RECORD + ".hang"):
    time.sleep(3600)
open(argv[argv.index("-o") + 1], "w").write('{{"title": "x"}}')
print(json.dumps({{"type": "item.completed", "item": {{"type": "agent_message", "text": '{{"title": "x"}}'}}}}), flush=True)
print(json.dumps({{"type": "turn.completed", "usage": {{"input_tokens": 12, "output_tokens": 5}}}}), flush=True)
"""


@pytest.fixture
def codex(tmp_path, monkeypatch) -> Path:
    """A fake codex first on PATH; returns the file it records into. Secrets the adapter must keep out of the child are set."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "codex"
    record = tmp_path / "record.json"
    exe.write_text(FAKE.replace("@RECORD@", str(record)), encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-bill")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-bill")
    monkeypatch.setenv("KEEP_ME", "yes")
    return Path(record)


def recorded(path: Path) -> dict[str, Any]:
    seen: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return seen


def wait_for_file(path: Path, seconds: float = 30.0) -> None:
    """Block until the fake has recorded itself (it renames the record into place, so the name is the signal)."""
    deadline = time.monotonic() + seconds
    while not path.exists():
        assert time.monotonic() < deadline, "the fake codex never started"
        time.sleep(0.01)


def flag(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


def test_schema_reaches_codex_as_a_file_and_usage_comes_back(codex):
    result = asyncio.run(CodexCliAdapter(env=os.environ).complete(user="q", system="rules", model="m1", response_schema=SCHEMA))
    seen = recorded(codex)
    assert json.loads(result.text) == {"title": "x"}
    assert (result.prompt_tokens, result.completion_tokens, result.model) == (12, 5, "m1")
    assert json.loads(seen["schema"]) == SCHEMA
    assert not Path(flag(seen["argv"], "--output-schema")).exists()  # the temp file is gone once the call ends
    assert seen["stdin"] == "rules\n\nq"


def test_no_schema_means_no_schema_flag(codex):
    asyncio.run(CodexCliAdapter(env=os.environ).complete(user="q"))
    assert "--output-schema" not in recorded(codex)["argv"]


@pytest.mark.parametrize(("effort", "sent"), [(None, "low"), ("low", "low"), ("medium", "medium"), ("high", "high")])
def test_effort_is_passed_and_defaults_to_low(codex, effort, sent):
    asyncio.run(CodexCliAdapter(env=os.environ).complete(user="q", effort=effort))
    assert flag(recorded(codex)["argv"], "-c") == f'model_reasoning_effort="{sent}"'


def test_unknown_effort_is_refused_before_launch(codex):
    with pytest.raises(AnyLLMError) as caught:
        asyncio.run(CodexCliAdapter(env=os.environ).complete(user="q", effort="extreme"))  # type: ignore[arg-type]  # the refusal under test
    assert not caught.value.retryable
    assert not codex.exists()


def test_child_is_isolated_and_holds_no_api_key(codex):
    asyncio.run(CodexCliAdapter(env=os.environ).complete(user="q"))
    seen = recorded(codex)
    argv = seen["argv"]
    assert all(f in argv for f in ("--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"))
    assert flag(argv, "--sandbox") == "read-only"
    assert seen["cwd_files"] == []  # an empty directory
    assert Path(seen["cwd"]).resolve() != Path.cwd().resolve()
    assert seen["env"] == {
        "ANTHROPIC_API_KEY": None,
        "OPENAI_API_KEY": None,
        "KEEP_ME": None,
    }  # the child gets an allow list, not the environment


@pytest.mark.parametrize("adapter", [ClaudeCodeCliAdapter, ClaudeCodeSdkAdapter, AnthropicApiAdapter, OpenAICompatibleAdapter])
def test_a_provider_that_cannot_enforce_a_schema_is_refused_loudly(adapter):
    with pytest.raises(AnyLLMError) as caught:
        require_structured(adapter(env=os.environ))
    assert not caught.value.retryable
    assert caught.value.hint


def test_codex_is_the_structured_provider():
    assert require_structured(CodexCliAdapter(env=os.environ)).name == "codex-cli"


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_cancel_kills_the_child_and_reraises(codex):
    Path(f"{codex}.hang").touch()

    async def scenario() -> tuple[bool, bool]:
        task = asyncio.ensure_future(CodexCliAdapter(env=os.environ).complete(user="q"))
        await asyncio.to_thread(wait_for_file, codex)
        pid = int(recorded(codex)["pid"])
        try:
            task.cancel()
            done, _ = await asyncio.wait({task}, timeout=30)
            return bool(done) and task.cancelled(), alive(pid)
        finally:
            with contextlib.suppress(ProcessLookupError):  # a red run must not leave the hanging fake (and asyncio.run's join) behind
                os.kill(pid, signal.SIGKILL)

    cancelled, child_alive = asyncio.run(scenario())
    assert cancelled  # CancelledError reached the caller within the bound
    assert not child_alive  # reaped before the caller saw the cancel
