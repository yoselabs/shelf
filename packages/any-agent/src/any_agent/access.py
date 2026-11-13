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
    exclude_slash_tmp: bool | None = None  # workspace-write: /tmp is not writable by default; None = codex's own default
    exclude_tmpdir: bool | None = None  # workspace-write: $TMPDIR is not writable by default; None = codex's own default
    tool_output_token_limit: int | None = None
    ignore_user_config: bool = False  # `exec` only: the person's config.toml is not read
    ignore_rules: bool = False  # `exec` only: the person's exec rules are not read
    shell_env: tuple[tuple[str, str], ...] = ()  # variables only the agent's shell commands get (shell_environment_policy.set)

    def __post_init__(self) -> None:
        CodexSandbox(self.sandbox)  # a plain string must be one of the closed vocabulary
        if self.approval is not None:
            CodexApproval(self.approval)
        tuned = (self.network, self.exclude_slash_tmp, self.exclude_tmpdir)
        if self.sandbox != CodexSandbox.WORKSPACE_WRITE and (any(t is not None for t in tuned) or self.writable_roots):
            msg = "codex network, writable_roots and the temp-folder exclusions apply to the workspace-write sandbox only"
            raise ValueError(msg)
        if self.tool_output_token_limit is not None and self.tool_output_token_limit <= 0:
            msg = "codex tool_output_token_limit must be positive"
            raise ValueError(msg)
        bad = [r for r in self.writable_roots if not r.startswith("/")]
        if bad:
            msg = f"codex writable_roots must be absolute: {', '.join(bad)}"
            raise ValueError(msg)

    def flags(self) -> list[str]:
        """The `codex exec` options of this policy (`codex sandbox` takes none of them)."""
        return [f for f, on in (("--ignore-user-config", self.ignore_user_config), ("--ignore-rules", self.ignore_rules)) if on]

    def config(self) -> list[str]:
        """The `-c key=value` flags the choices beyond the sandbox mode itself need; `exec` and `sandbox` both take them."""
        pairs: list[tuple[str, object]] = []
        if self.approval is not None:
            pairs.append(("approval_policy", str(self.approval)))
        pairs += [("sandbox_workspace_write." + k, v) for k, v in self._write_keys()]
        if self.tool_output_token_limit is not None:
            pairs.append(("tool_output_token_limit", self.tool_output_token_limit))
        pairs += [("shell_environment_policy.set." + k, v) for k, v in self.shell_env]
        return [part for k, v in pairs for part in ("-c", f"{k}={json.dumps(v)}")]

    def _write_keys(self) -> list[tuple[str, object]]:
        keys: list[tuple[str, object]] = [
            ("network_access", self.network),
            ("exclude_slash_tmp", self.exclude_slash_tmp),
            ("exclude_tmpdir_env_var", self.exclude_tmpdir),
        ]
        keys = [(k, v) for k, v in keys if v is not None]
        return keys + ([("writable_roots", list(self.writable_roots))] if self.writable_roots else [])

    def sandbox_argv(self, exe: str, command: list[str]) -> list[str]:
        """`codex sandbox` running `command` under this policy: the mode as a config key, then `config()`. The person's Codex config is
        read beneath these keys, as `codex sandbox` has no `--ignore-user-config`; the use of this to prove the host can enforce the
        policy before a launch is the caller's."""
        return [exe, "sandbox", "-c", "sandbox_mode=" + json.dumps(str(self.sandbox)), *self.config(), "--", *command]


type AccessPolicy = ClaudeAccess | CodexAccess


def refuse(kind: str, access: AccessPolicy) -> NoReturn:
    msg = f"{kind} cannot take a {type(access).__name__} access policy"
    raise ValueError(msg)
