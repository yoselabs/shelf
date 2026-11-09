# Existing builder owns each syntax

Baseline delivered9787eb9fba1025c7808fd310894e18e9fa05cb44. Change only
LaunchInputs/CodexHarness and their consumers/tests/docs. Fresh and resume share
semantic model/effort choices, with their supported sandbox syntax: fresh -s;
resume -c sandbox_mode=<quoted-string>. LaunchSpec.cwd sets process cwd for both,
so no unsupported resume -C or duplicate cwd authority is introduced.

Empty optional model/effort/sandbox means omission/native configuration, never an
invented read-only default. Empty output/schema means omission; existing Codex
summary falls back to stream messages without an output file. Refuse empty/blank
nonsealed exe/cwd and explicit empty resume. Preserve access/isolation verbatim;
those existing flag-list capabilities are not redesigned in this slice. TOML string
config values use the existing json string encoder to retain one literal value.

Sealed branches return before these nonsealed rules; sealed Codex/Claude launches,
login and subscription safeguards stay intact. No model invocation is needed.
Local codex-cli0.167.0 exec/resume --help confirmed common model/config/schema/output/
JSON options and resume's absence of -s. Full fresh and resume option combinations
were also accepted with --help; this proves syntax only, not model execution.
Evidence: /tmp/shelf-evlp-codex-exec-help.txt and -resume-help.txt;
/tmp/shelf-evlp-fresh-syntax-help.txt and -resume-syntax-help.txt.

Tests first: semantic final-spec assertions without cli, resume/schema preservation,
empty omission/refusal and literal effort configuration produced9 failed/28 passed
before implementation (/tmp/shelf-evlp-red.log). Migrate the old handbuilt fixture
to typed LaunchInputs; remove its Any annotation rather than introduce another one.
Required focused contracts, normal/full Linux gates, independent final review and
exact-tree Mac verification precede delivery. Candidate metadata/REQUEST ledger
record demand only. No factory source, remote/tag/install or task-state writes.
