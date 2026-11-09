# Separate blueprint gate domains

Owner: blueprint. Task: shelf-50w.1, child of shelf-50w.

The PR66 integration gate rejects `concerns/gate.py` at 641 source lines against the
400-line cap. Separate existing behavior by ownership while preserving checkpoint
IDs, statements, versions, audit selection, order and findings.

This bounded repair does not complete shelf-50w: shared workflow-model adoption in
facts and Python pin checks, and before/after snapshots of all consumer repos,
remain with that parent. No thresholds, severity, global gate configuration or
compatibility import paths change.
