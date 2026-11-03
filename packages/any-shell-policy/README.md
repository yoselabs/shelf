# any-shell-policy

Stop hand-rolling shell-text guards. Parse a command line quote-aware into simple commands, then run
rules over it. Stdlib only, so a stdlib-only plugin can vendor it.

```python
from any_shell_policy import judge, parse


def no_kill_by_name(tool, args):
    commands = parse(str(args.get("command") or "")) if tool == "Bash" else []
    if any(c.name in {"pkill", "killall"} for c in commands or []):
        return "kill the PID you started, not a process name"
    return ""


assert judge([no_kill_by_name], "Bash", {"command": "ls && sudo sh -c 'pkill x'"}).blocked
assert not judge([no_kill_by_name], "Bash", {"command": "echo 'a;pkill'"}).blocked
```

## What it looks through

| input | result |
|---|---|
| `a \| b && c ; d`, newline, `(a)`, `` `a` ``, `$(a)` | separate commands |
| `echo 'x;y' "p\|q"` | one command; quoted separators stay in the word |
| `sudo env A=1 nohup pkill x` | `Command.name == "pkill"`; `strip_wrappers` gives the words |
| `sh -c '...'`, `bash -lc`, `eval`, `bash <<EOF` | replaced by the script's commands, nested to depth 3 |
| `A=1 B=2 cmd` | `assigns` split from `argv` |
| `cmd > out 2>>log`, `> /dev/null`, `2>&1` | `redirects` keeps the first two, drops the quiet ones |
| `cat <<EOF ... EOF` | body is `Command.stdin`, never parsed as commands |

## Not a security boundary

A rule over `parse` is a tripwire for accidents and lazy injections, not a sandbox. It does not see:

- a shell fed by a pipe: `echo 'git push' | sh`, `cat <<EOF | sh`
- a substitution inside double quotes: `echo "$(git push)"` (`has_write_syntax` flags it as text, nothing more)
- variable expansion, `$'..'` decoding, aliases, functions defined elsewhere
- launchers that run a command string: `busybox`, `coproc`, `find -exec`, `ssh host`, `xargs sh`-style tools outside `WRAPPERS`

**`parse` returns `None` for an unclosed quote, `$'...'`, or `sh -c` nested deeper than 3: treat `None` as
a block.** A guard that allows on `None` lets the one input it could not read through. It never raises.

`has_write_syntax(text)` is the quote-blind check for output redirects and substitutions (a `>` inside
quotes counts). `strip_excluded(argv)` drops `rg --glob '!x'`, `grep --exclude`, `find -not -path`, git
`':!x'` so a guard scanning for secret paths does not trip on a path the call only excludes.

Public: `parse`, `Command`, `judge`, `Rule`, `Verdict`, `has_write_syntax`, `strip_excluded`. Helpers in
the submodules (`strip_wrappers`, `name_of`, `is_assign`, `strip_heredocs`, `WRAPPERS`, `SHELLS`,
`MAX_DEPTH`) are unstable and may change without notice.
