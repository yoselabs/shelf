"""Typed access policy: what a worker may do, chosen by the caller as a closed vocabulary instead of raw vendor flags.

A harness translates the policy that matches its kind and refuses another kind's. Absent (`LaunchInputs.access is None`) every harness
keeps its default: claude `auto` mode with the caller's `settings`, codex the caller's `sandbox` and `access` flags. OpenCode's access is
its `Sandbox` (see `opencode_sandbox`), given to the harness at construction.
"""

import enum
import json
from typing import NoReturn

from any_agent._json import record


class ClaudePermissionMode(enum.StrEnum):
    """`claude --permission-mode`."""

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    AUTO = "auto"
    DONT_ASK = "dontAsk"


class CodexSandbox(enum.StrEnum):
    """`codex exec --sandbox`."""

    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


class CodexApproval(enum.StrEnum):
    """codex `approval_policy`."""

    NEVER = "never"
    ON_REQUEST = "on-request"
    ON_FAILURE = "on-failure"
    UNTRUSTED = "untrusted"


@record
class ClaudeAccess:
    permission_mode: ClaudePermissionMode = ClaudePermissionMode.AUTO
    settings: str = ""  # `--settings` JSON; empty = LaunchInputs.settings

    def __post_init__(self) -> None:
        ClaudePermissionMode(self.permission_mode)  # a plain string must be one of the closed vocabulary
        if self.settings:
            try:
                parsed = json.loads(self.settings)
            except ValueError as x:
                msg = f"claude settings are not JSON: {x}"
                raise ValueError(msg) from x
            if not isinstance(parsed, dict):
                msg = "claude settings must be a JSON object"
                raise ValueError(msg)


@record
class CodexAccess:
    sandbox: CodexSandbox = CodexSandbox.WORKSPACE_WRITE
    approval: CodexApproval | None = None  # None = codex's own default
    network: bool | None = None  # workspace-write network access; None = codex's own default
    writable_roots: tuple[str, ...] = ()  # workspace-write extra writable folders, absolute

    def __post_init__(self) -> None:
        CodexSandbox(self.sandbox)  # a plain string must be one of the closed vocabulary
        if self.approval is not None:
            CodexApproval(self.approval)
        if self.sandbox != CodexSandbox.WORKSPACE_WRITE and (self.network is not None or self.writable_roots):
            msg = "codex network and writable_roots apply to the workspace-write sandbox only"
            raise ValueError(msg)
        bad = [r for r in self.writable_roots if not r.startswith("/")]
        if bad:
            msg = f"codex writable_roots must be absolute: {', '.join(bad)}"
            raise ValueError(msg)

    def config(self) -> list[str]:
        """The `-c key=value` flags the choices beyond the sandbox itself need."""
        out: list[str] = []
        if self.approval is not None:
            out += ["-c", "approval_policy=" + json.dumps(str(self.approval))]
        if self.network is not None:
            out += ["-c", "sandbox_workspace_write.network_access=" + json.dumps(self.network)]
        if self.writable_roots:
            out += ["-c", "sandbox_workspace_write.writable_roots=" + json.dumps(list(self.writable_roots))]
        return out


type AccessPolicy = ClaudeAccess | CodexAccess


def refuse(kind: str, access: AccessPolicy) -> NoReturn:
    msg = f"{kind} cannot take a {type(access).__name__} access policy"
    raise ValueError(msg)
