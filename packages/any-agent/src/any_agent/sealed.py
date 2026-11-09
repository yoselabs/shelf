"""The sealed launch: a pure completion. Only the caller's system and user text reach the model.

A sealed launch is a launch with every list empty: no tools, MCP servers, skills, hooks, memory, plugins, project or user instructions,
no default coding prompt, one turn, an explicit model. Each harness maps it to its own CLI's flags; this module holds what they share:
the empty directory the child runs in, so a project's own instruction files (CLAUDE.md, AGENTS.md, .mcp.json) are never found from cwd.
"""

import tempfile
from pathlib import Path


class SealedDir:
    """An empty directory one sealed launch runs in, removed by `cleanup`."""

    def __init__(self, prefix: str) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix=prefix)
        self.path = Path(self._temp.name)

    def cleanup(self) -> None:
        self._temp.cleanup()
