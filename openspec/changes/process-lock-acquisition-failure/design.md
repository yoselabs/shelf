# One descriptor owner during acquisition

The previous private `_lock` returned the descriptor after flock and metadata writing,
then `_try` constructed its registry entry. `_write` lay outside the close-on-error
scope, holder observation lay inside an exception handler that could itself raise,
and registry construction was unprotected after `_lock` returned.

Collapse the private helper into `_try`, which already holds the registry mutex.
A single finally region covers every operation after the descriptor is opened.
The existing registry entry is the ownership handoff: until that entry owns this
FD, the acquisition closes it. No redundant ownership flag or new resource class.
Once registered, the existing reference-counted release remains its owner.

Keep acquire's existing metadata prevalidation. The serialization regression injects
failure at the second, post-flock serialization, not the already-safe prevalidation.
Other cases inject native pwrite/ftruncate failure, registry construction failure and
KeyboardInterrupt after flock. Each calls public acquire, observes the actual error,
and asks a real independent process to acquire the path before any test cleanup.
A refused holder read failure must close only its observation FD while the actual
foreign holder remains exclusive; after that holder releases, a contender succeeds.
Regression teardown closes only captured descriptors matching the test's owned inode,
so demonstrating the old bug leaves no leaked lock or child behind.

This patch does not prove descendant custody after process death or add inheritance,
process observation, a fake process platform, or factory integration. Linux gates,
independent review and exact-final-tree native verification precede publication.
