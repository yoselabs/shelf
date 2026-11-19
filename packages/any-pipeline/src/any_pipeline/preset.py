"""A ruff preset for modules that build pipelines: the raw tools this package replaces are banned, with the reason."""

from __future__ import annotations

BANNED = {
    "threading": "no hand-made threads: a blocking call goes through any_pipeline.blocking",
    "concurrent.futures": "no thread or process pools: a stage is async, a child process is a stage",
    "asyncio.gather": "a failed branch leaves its siblings running: use any_pipeline.gather (a TaskGroup)",
    "asyncio.create_task": "a task nobody awaits is lost with its error: use a TaskGroup (any_pipeline.gather)",
    "time.sleep": "a sleep blocks the loop: await asyncio.sleep, or let a Limit bound the retries",
}


def ruff_config() -> str:
    """The preset as ruff.toml text: the bans, bare `except:`, and blocking calls inside `async def`."""
    bans = "\n".join(f'"{name}" = {{ msg = "{why}" }}' for name, why in BANNED.items())
    return f'[lint]\nselect = ["TID251", "E722", "ASYNC"]\n\n[lint.flake8-tidy-imports.banned-api]\n{bans}\n'
