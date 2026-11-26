import argparse
import os
from pathlib import Path
import re
import sys
from uuid import uuid4


def destination(directory, data):
    fields = re.fullmatch(
        r"# ([^\r\n]+)\nID: ([A-Za-z0-9._-]+)\nRun: ([^\r\n]+)\n"
        r"Task: ([^\r\n]+)\nDispatch: ([^\r\n]+)\nNext: ([^\r\n]+)\n",
        data.decode("utf-8"),
    )
    if not fields or not all(value.strip() for value in fields.groups()):
        raise ValueError("expected six nonempty LF-terminated handoff fields")
    key = fields[2]
    if key in (".", ".."):
        raise ValueError("invalid handoff ID")
    directory = directory.resolve(strict=True)
    final = directory / (key + ".md")
    if not directory.is_dir() or final.resolve().parent != directory:
        raise ValueError("invalid handoff directory or destination")
    return final


def publish(final, data):
    temporary = final.parent / f".handoff-{uuid4().hex}"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
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
    parser = argparse.ArgumentParser(prog="conflux.py handoff", allow_abbrev=False)
    parser.add_argument("action", choices=("publish", "verify"))
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--file", required=True)
    args = parser.parse_args(argv)
    try:
        data = sys.stdin.buffer.read() if args.file == "-" else Path(args.file).read_bytes()
        final = destination(args.dir, data)
        if args.action == "publish":
            return publish(final, data)
        return 0 if final.read_bytes() == data else 11
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
