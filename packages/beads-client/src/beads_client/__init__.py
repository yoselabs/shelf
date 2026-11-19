"""beads-client: a lean, typed, fail-loud client over the bd CLI. Stdlib and child-env only; imports no host."""

from beads_client.client import TESTED_BELOW, TESTED_FROM, Bd, SyncResult
from beads_client.errors import BdError, ErrorKind
from beads_client.reads import ReadyReadClient, TaskReadClient
from beads_client.records import DEP_BLOCKS, Bead, BeadStatus, Comment, Dep, NewBead
from beads_client.runner import BdRun, Runner, subprocess_runner

__all__ = [
    "DEP_BLOCKS",
    "TESTED_BELOW",
    "TESTED_FROM",
    "Bd",
    "BdError",
    "BdRun",
    "Bead",
    "BeadStatus",
    "Comment",
    "Dep",
    "ErrorKind",
    "NewBead",
    "ReadyReadClient",
    "Runner",
    "SyncResult",
    "TaskReadClient",
    "subprocess_runner",
]
