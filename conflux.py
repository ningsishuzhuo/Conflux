import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys


from conflux_handoff import handoff


DATA_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError)
ROUTE_KEY = ("agent", "profile", "model")
ROUTE_FIELDS = {*ROUTE_KEY, "billing", "keep_open_default"}
BILLING = ("subscription", "low_cost", "paid")
BLOCKED = {"--agent", "--profile", "--model", "--cwd"}


def unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("duplicate JSON field")
    return fields


def load_routes(path):
    policy = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    if not isinstance(policy, dict) or set(policy) != {"routes"} or not isinstance(policy["routes"], list):
        raise ValueError("policy must contain only a routes list")
    routes = {}
    for route in policy["routes"]:
        if (
            not isinstance(route, dict)
            or set(route) != ROUTE_FIELDS
            or any(not isinstance(route[field], str) or not route[field].strip()
                   for field in ROUTE_KEY)
            or route["billing"] not in BILLING
            or not isinstance(route["keep_open_default"], bool)
        ):
            raise ValueError("invalid policy route")
        key = tuple(route[field] for field in ROUTE_KEY)
        if key in routes:
            raise ValueError("duplicate policy route")
        routes[key] = route
    return routes


def utc(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    stamp = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    return stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).astimezone(timezone.utc)


def ledger_rows(path):
    try:
        with path.open("rb") as source:
            for number, line in enumerate(source, 1):
                try:
                    if line.strip():
                        yield json.loads(line)
                except ValueError:
                    print(f"warning: skipping damaged ledger line {number}: {path}", file=sys.stderr)
    except FileNotFoundError:
        return

def window(path, now):
    start = now - timedelta(hours=5)
    agents = {row["dispatch_id"]: row["agent"] for row in ledger_rows(path)
              if start < utc(row["ts"]) <= now}
    counts = Counter(agents.values())
    agy, codex = counts["antigravity"], counts["codex"]
    return dict(window_hours=5, agy_calls=agy, codex_calls=codex,
                other_calls=len(agents) - agy - codex,
                agy_allowed_next=2 * (agy + 1) < codex,
                metric_kind="conflux_dispatch_proxy")


def append_receipt(path, output, now, route):
    try:
        receipt = json.loads(output)
    except ValueError:
        receipt = {}
    sources = (receipt, receipt.get("result")) if isinstance(receipt, dict) else ()
    ids = (item.get("dispatchId") for item in sources if isinstance(item, dict))
    key = next((key for key in ids if isinstance(key, str) and key.strip()), None)
    if key is None:
        print("\nwarning: Orca receipt has no dispatchId", file=sys.stderr)
        return
    row = dict(ts=now.isoformat().replace("+00:00", "Z"), dispatch_id=key,
               **{field: route[field] for field in (*ROUTE_KEY, "billing")})
    with path.with_name(path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if any(existing["dispatch_id"] == key for existing in ledger_rows(path)):
            return
        with path.open("a+b") as ledger:
            if ledger.tell():
                ledger.seek(-1, 2)
            prefix = b"\n" if ledger.read(1) not in (b"", b"\n") else b""
            ledger.write(prefix + (json.dumps(row) + "\n").encode())


def codex_tokens(path, now):
    start = now - timedelta(hours=5)
    tokens, seen = 0, set()
    evidence = dict(path=str(path))
    with path.open(encoding="utf-8") as source:
        rows = (json.loads(line) for line in source if line.strip())
        events = sorted(((utc(row["timestamp"]), row.get("payload", row))
                         for row in rows), key=lambda item: item[0])
    has_baseline = bool(events and events[0][0] > start)
    previous = 0 if has_baseline else None
    for stamp, event in events:
        if event.get("type") != "token_count":
            continue
        if stamp > now:
            continue
        info = event.get("info")
        info = event if info is None else info
        total, delta = (({} if usage is None else usage).get("total_tokens")
                         for usage in map(info.get, ("total_token_usage", "last_token_usage")))
        if stamp <= start:
            has_baseline = True
            if total is not None:
                previous = total
            continue
        if not has_baseline or (total is not None and previous is None):
            return dict(evidence, status="missing_baseline")
        if total is not None:
            if total < previous:
                return dict(evidence, status="counter_reset")
            tokens += total - previous
            previous = total
        elif delta is not None and (stamp, delta) not in seen:
            tokens += delta
            seen.add((stamp, delta))
            if previous is not None:
                previous += delta
    return dict(evidence, status="ok", total_tokens=tokens)


def usage(argv):
    parser = argparse.ArgumentParser(prog="conflux.py usage", allow_abbrev=False)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--codex-jsonl", action="append", type=Path, default=[])
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    try:
        now = utc(args.now)
        result = window(args.ledger, now)
        if args.codex_jsonl:
            paths = dict.fromkeys(path.resolve() for path in args.codex_jsonl)
            result["codex_tokens"] = [codex_tokens(path, now) for path in paths]
    except DATA_ERRORS as error:
        parser.error(f"cannot read usage: {error}")
    print(json.dumps(result))
    return 0


def main(argv):
    if argv and (handler := {"usage": usage, "handoff": handoff}.get(argv[0])):
        return handler(argv[1:])
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("command", choices=("dispatch",))
    parser.add_argument("--policy", required=True, type=Path)
    for field in ROUTE_KEY:
        parser.add_argument(f"--{field}", required=True)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--authorize-paid", default="")
    parser.add_argument("--orca-bin", default="orca")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--now")

    separator = argv.index("--") if "--" in argv else len(argv)
    args = parser.parse_args(argv[:separator])
    if args.agent == "antigravity" and args.ledger is None:
        parser.error("antigravity requires --ledger")
    native = argv[separator + 1:]
    try:
        routes = load_routes(args.policy)
    except (OSError, ValueError) as error:
        parser.error(f"cannot load policy: {error}")
    route = routes.get((args.agent, args.profile, args.model))
    if route is None:
        parser.error("unknown policy route")
    if route["billing"] == "paid" and not args.authorize_paid.strip():
        parser.error("paid route requires --authorize-paid with a nonblank reason")
    if not args.cwd.is_dir():
        parser.error("--cwd must be an existing directory")
    for token in native:
        if (flag := token.partition("=")[0]) in BLOCKED:
            parser.error(f"Orca arguments cannot override {flag}")

    if args.ledger is not None:
        args.ledger = args.ledger.resolve()
    if args.agent == "antigravity":
        try:
            if not window(args.ledger, utc(args.now))["agy_allowed_next"]:
                parser.error("antigravity exceeds the 5-hour dispatch ratio")
        except DATA_ERRORS as error:
            parser.error(f"cannot read ledger: {error}")
    binary = str(Path(args.orca_bin).absolute()) if "/" in args.orca_bin else args.orca_bin
    command = [binary, "orchestration", "worker-start", "--agent", args.agent, *([] if args.model == "default" else ["--model", args.model]), *native]
    if route["keep_open_default"] and "--keep-open" not in native:
        command.append("--keep-open")
    try:
        result = subprocess.run(command, cwd=args.cwd, stdout=subprocess.PIPE if args.ledger else None)
    except OSError as error:
        print(error, file=sys.stderr)
        return 127 if isinstance(error, FileNotFoundError) else 126
    if args.ledger is not None:
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.buffer.flush()
        if result.returncode == 0:
            try:
                append_receipt(args.ledger, result.stdout, utc(args.now), route)
            except DATA_ERRORS as error:
                print(f"cannot append ledger: {error}", file=sys.stderr)
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
