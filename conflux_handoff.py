import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import re
import sys
from uuid import uuid4


@contextmanager
def exclusive_lock(path):
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            from time import sleep
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                sleep(0.02)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


HANDOFF_FORMAT = """Expected six nonempty UTF-8 handoff lines, each ending in LF:
# <Title>
ID: <id>
Run: <run>
Task: <task>
Dispatch: <dispatch>
Next: <next>"""


def handoff_id(content):
    if "\r" in content:
        raise ValueError("CRLF or bare CR is invalid; use LF line endings")
    if content and not content.endswith("\n"):
        raise ValueError("handoff ends without a final LF")
    lines = content.split("\n")[:-1]
    if len(lines) != 6:
        raise ValueError(f"expected six lines; got {len(lines)}")
    for number, (line, template) in enumerate(zip(lines, HANDOFF_FORMAT.split("\n")[1:]), 1):
        prefix = template.partition("<")[0]
        if not line.startswith(prefix):
            raise ValueError(f"line {number}: expected field prefix {prefix!r}")
        if not line[len(prefix):].strip():
            raise ValueError(f"line {number}: empty value for {prefix.strip()}")
    key = lines[1].removeprefix("ID: ")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", key) or key in (".", ".."):
        raise ValueError("invalid ID: use letters, digits, '.', '_' or '-'; '.' and '..' are reserved")
    return key


def publish(final, data):
    temporary = final.parent / f".handoff-{uuid4().hex}"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, final)
        except FileExistsError:
            return 10 if final.read_bytes() == data else 11
        return 0 if final.read_bytes() == data else 11
    finally:
        temporary.unlink()


def handoff(argv):
    parser = argparse.ArgumentParser(
        prog="conflux.py handoff", allow_abbrev=False, epilog=HANDOFF_FORMAT,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("publish", "verify"))
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--file", required=True)
    args = parser.parse_args(argv)
    try:
        data = sys.stdin.buffer.read() if args.file == "-" else Path(args.file).read_bytes()
        key = handoff_id(data.decode("utf-8"))
        directory = args.dir.resolve(strict=True)
        final = directory / (key + ".md")
        if not directory.is_dir() or final.resolve().parent != directory:
            raise OSError("invalid handoff directory or destination")
        if args.action == "publish":
            return publish(final, data)
        return 0 if final.read_bytes() == data else 11
    except ValueError as error:
        parser.error(f"{error}\n{HANDOFF_FORMAT}")
    except (OSError, RuntimeError) as error:
        parser.error(str(error))
