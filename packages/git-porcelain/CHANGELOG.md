# Changelog

## 0.13.0

- `RealRepo(..., ambient=<mapping>)`: a snapshot of the ambient environment taken once, so a call neither scans `os.environ` nor searches `PATH` (30,000 calls: 1.8 s to 0.01 s). Without it each call still reads the process environment as it is then.

## 0.12.1

- A fetch that loses the race to create a ref (git 2.53: `fetching ref <ref> failed: reference already exists`) is a retryable `RefRace`, like the older lock wording.
