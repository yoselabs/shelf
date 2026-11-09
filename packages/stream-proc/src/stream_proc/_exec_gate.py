"""Isolated installed bootstrap. No package, cwd or user startup imports before permit."""

from __future__ import annotations

import argparse
import contextlib
import errno
import json
import math
import os
import select
import struct
import sys
import time

MAX_FRAME = 8 * 1024 * 1024


class GateArguments(argparse.Namespace):
    control: int
    status: int
    timeout: float


def private_fd(value: str) -> int:
    result = int(value)
    if result < 3:
        msg = "a private descriptor must be at least 3"
        raise argparse.ArgumentTypeError(msg)
    return result


def positive_timeout(value: str) -> float:
    result = float(value)
    if result <= 0 or not math.isfinite(result):
        msg = "registration timeout must be finite and positive"
        raise argparse.ArgumentTypeError(msg)
    return result


def arguments() -> tuple[int, int, float]:
    parser = argparse.ArgumentParser(description="Execute a target only after durable process registration permits it.")
    parser.add_argument("control", type=private_fd, help="Private descriptor carrying the framed execution permission.")
    parser.add_argument("status", type=private_fd, help="Private descriptor reporting bootstrap readiness and exec errors.")
    parser.add_argument("timeout", type=positive_timeout, help="Maximum registration wait in seconds.")
    parsed = GateArguments()
    parser.parse_args(namespace=parsed)
    if parsed.control == parsed.status:
        parser.error("control and status descriptors must differ")
    return parsed.control, parsed.status, parsed.timeout


def read_exact(fd: int, size: int, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise TimeoutError
        chunk = os.read(fd, size - len(data))
        if not chunk:
            raise EOFError
        data.extend(chunk)
    return bytes(data)


def invocation(raw: bytes) -> tuple[list[str], dict[str, str]]:
    value: object = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"permit", "argv", "env"} or value["permit"] != "exec":
        raise ValueError
    argv, env = value["argv"], value["env"]
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or "\0" in arg for arg in argv):
        raise ValueError
    if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) or "\0" in k + v for k, v in env.items()):
        raise ValueError
    return argv, env


def permitted(control: int, deadline: float) -> tuple[list[str], dict[str, str]]:
    size = int.from_bytes(read_exact(control, 4, deadline), "big")
    if not 0 < size <= MAX_FRAME:
        raise ValueError
    return invocation(read_exact(control, size, deadline))


def main() -> int:
    control, status, timeout = arguments()
    inherit = False
    try:
        os.set_inheritable(control, inherit)
        os.set_inheritable(status, inherit)
        os.write(status, b"R")
        deadline = time.monotonic() + timeout
        argv, env = permitted(control, deadline)
        os.close(control)
        os.execvpe(argv[0], argv, env)
    except TimeoutError:
        number = errno.ETIMEDOUT
    except OSError as error:
        number = error.errno or errno.EIO
    except (EOFError, ValueError, TypeError, RecursionError):
        number = errno.EPROTO
    payload = struct.pack("!I", number)
    with contextlib.suppress(BrokenPipeError):
        os.write(status, payload)
    return 127


if __name__ == "__main__":
    sys.exit(main())
