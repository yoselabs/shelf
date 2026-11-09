# Registration before target execution

`popen_registered` owns one real Popen plus private permit and startup-status pipes.
It invokes the installed `_exec_gate.py` by absolute path using `-I -S`; the gate
imports isolated stdlib only, never package/cwd/user startup code. stdin remains the
prompt pipe, stdout/stderr retain normal target semantics, and the target replaces
the bootstrap in the same PID and session. The parent sends the original environment
in its private frame so Python bootstrap locale coercion cannot change target input.

The gate reports readiness; native identity is acquired before the registration
callback. The callback must commit durably and return within its owning persistence
bound. Only then can the parent send a complete length-prefixed exec permission.
EOF, partial/malformed/oversized frames and timeout do not execute the target.
Exec errors return native errno privately; stderr is not a control protocol.
Held callable SIGTERM/SIGINT handlers replay inside child cleanup while permission
is withheld. Callback BaseException and live-sink failure also remain behind the gate.
There is no invented process-stop report for a target that never executed.

The required `os.execvpe` is an explicit S606 exception owned in root configuration
for this one installed gate file. Caller argv is trusted, no shell/parser is involved,
private payload is validated, and exec is required to preserve the registered PID.
Literal shell-looking arguments are tested as literal argv. No dynamic getattr or
source suppression hides the mechanism.

`OwnedProcess` carries PID, observed process group, native start token and boot UUID.
`ProcessObservation` distinguishes matching, gone, different_process and unknown.
The owning native readers preserve inaccessible/malformed reads; existing table APIs
still consume the same reader. Boot UUID is `/proc/sys/kernel/random/boot_id` on Linux;
macOS uses native sysctlbyname kern.bootsessionuuid and existing libproc start identity.
Unsupported/denied native reads remain unknown and forbid launch. Apple defines this
read-only boot session UUID in its kernel source:
https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/kern/kern_sysctl.c

Cleanup acts only on the freshly owned Popen, with bounded waits. Observation is of
the leader, not whole-workload proof. After permission, abrupt bootstrap/target death
can remain uncertain: successful return means registered permission, not proof of
harness execution. No process-group proof, surviving descendants, supervisor lifetime,
coordinator restart/result collection, resource lock transfer or fake process platform
is claimed. These remain subsequent bounded owning changes.

Any-agent's existing started hook moves through procs.spawn into registration; its
Worker adds boot identity and a required start token. The duplicate postspawn hook
is removed. The live sink is called behind the same gate, so failure cannot let the
target execute. Existing harnesses and synchronous supervision remain the consumer.

Once permission transmission begins, an interruption/timeout/control-channel failure
raises `RegisteredStartUncertainError`, carrying the registered OwnedProcess and a
leader_reaped fact. The original failure is chained. The conservative phase is set
before the first permission write, avoiding a signal gap after the final write.
Confirmed errno rejection from the child remains a native OSError because that
specific private reply establishes exec failure. No exception with leader_reaped
claims descendants are stopped. Any-agent preserves its durable Worker callback and
propagates the uncertainty without an empty whole-workload-stop report.
