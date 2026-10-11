# A blueprint recipe (`blueprint recipe godot-test`): paste into the repo's justfile and add godot-test to `check`.
# Set godot_root to the folder holding project.godot. No backticks: `just --dry-run` evaluates them.

godot := env('GODOT', 'godot')
godot_root := "src/Game.Godot"

# In-engine view tests (Chickensoft GoDotTest). Fails on a failing test (exit 1), on any ERROR: line, and when no test
# ran (a missing --run-tests, a missing scene or a renamed entry runs zero tests and can exit 0).
godot-test:
    #!/usr/bin/env bash
    set -uo pipefail
    log=$(mktemp)
    "{{ godot }}" --headless --path "{{ godot_root }}" res://viewtests/TestEntry.tscn --run-tests --quit-on-finish > "$log" 2>&1
    rc=$?
    sed 's/\x1b\[[0-9;]*m//g' "$log" > "$log.txt"; rm -f "$log"
    if grep -q 'ERROR:' "$log.txt"; then grep -E 'ERROR:|Test failed|Test results' "$log.txt" >&2; rm -f "$log.txt"; echo "godot-test: engine errors above" >&2; exit 1; fi
    if [ "$rc" -eq 0 ] && ! grep -Eq 'Test results: Passed: [1-9]' "$log.txt"; then cat "$log.txt" >&2; rm -f "$log.txt"; echo "godot-test: no test ran" >&2; exit 1; fi
    [ "$rc" -eq 0 ] || cat "$log.txt" >&2
    rm -f "$log.txt"; exit "$rc"
