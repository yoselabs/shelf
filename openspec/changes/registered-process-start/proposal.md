# Registered process start

Task shelf-4426; factory consumer tl-8bh9.4.4.1.

The existing any-agent started hook runs after target execution has begun. Its spawn
helper also replays held signals before its caller owns cleanup. A real regression
observed a target writing its marker while registration was still blocked.

Add one stream-proc registration gate and use it from existing any-agent spawn.
Register a complete native boot/PID/start/group identity before permitting exec.
The isolated installed bootstrap exec-replaces itself; it is not another supervisor.
This change does not establish restart result collection, whole-tree stop proof,
lock transfer or a persistent execution service. Versions and publication stay separate.
