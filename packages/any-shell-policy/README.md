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

`parse` returns `None` for an unclosed quote, `$'...'`, or `sh -c` nested deeper than 3. Treat `None` as
"cannot tell" and choose: a block-list guard may allow (the shell will refuse it), an allow-list guard
must block. It never raises.

`has_write_syntax(text)` is the quote-blind check for output redirects and substitutions (a `>` inside
quotes counts). `strip_heredocs(text)` and `strip_excluded(argv)` (drop `rg --glob '!x'`, `grep --exclude`,
`find -not -path`, git `':!x'`) serve guards that scan the remaining text for secret paths.

Not modelled: variable expansion, a shell fed by a pipe (`echo x | sh`), `$(...)` inside double quotes
(see `has_write_syntax`), long wrapper options with a separate value outside `WRAPPERS`.
