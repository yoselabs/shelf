# Close acquisition descriptors until ownership transfers

Task shelf-7c34. The public acquire can raise after flock succeeds without returning
a handle or registering ownership. A real independent process then cannot acquire
the same path. Refused holder metadata observation can also leak its temporary FD.

Retain one native descriptor ownership region through flock, holder observation,
metadata writing and registry adoption. Close on every exit before that adoption.
Keep successful reentrancy, thread/process exclusion and release unchanged. No new
public API, polling, sidecar, inheritance operation or custody framework is needed.
