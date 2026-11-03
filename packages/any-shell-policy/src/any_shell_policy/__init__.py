"""Quote-aware shell command parsing and a first-block-wins rule runner, for guards over tool calls."""

from any_shell_policy.command import SHELLS, WRAPPERS, Command, is_assign, name_of, strip_wrappers
from any_shell_policy.excluded import strip_excluded
from any_shell_policy.judge import Rule, Verdict, judge
from any_shell_policy.parse import MAX_DEPTH, has_write_syntax, parse, strip_heredocs

__all__ = [
    "MAX_DEPTH",
    "SHELLS",
    "WRAPPERS",
    "Command",
    "Rule",
    "Verdict",
    "has_write_syntax",
    "is_assign",
    "judge",
    "name_of",
    "parse",
    "strip_excluded",
    "strip_heredocs",
    "strip_wrappers",
]
