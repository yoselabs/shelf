#!/usr/bin/env bash
# The fixture repo, copied into the empty workspace and committed.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp -R "$here/fixture/." .
git init -q -b main && git -c user.email=e@example.invalid -c user.name=e add -A
git -c user.email=e@example.invalid -c user.name=e commit -qm fixture
