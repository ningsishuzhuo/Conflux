import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


from conflux_handoff import exclusive_lock, handoff
from conflux_usage import DATA_ERRORS, ledger_rows, usage, user_path, utc, window


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


def append_receipt(path, output, now, route):
    try:
        receipt = json.loads(output)
    except ValueError:
        receipt = {}
    sources = (receipt, receipt.get("result")) if isinstance(receipt, dict) else ()
    key = next((item["dispatchId"] for item in sources if isinstance(item, dict)
                and isinstance(item.get("dispatchId"), str) and item["dispatchId"].strip()), None)
    if key is None:
        print("\nwarning: Orca receipt has no dispatchId", file=sys.stderr)
        return
    row = dict(ts=now.isoformat().replace("+00:00", "Z"), dispatch_id=key,
               **{field: route[field] for field in (*ROUTE_KEY, "billing")})
    with exclusive_lock(path.with_name(path.name + ".lock")):
        if any(existing["dispatch_id"] == key for existing in ledger_rows(path)):
            return
        with path.open("a+b") as ledger:
            if ledger.tell():
                ledger.seek(-1, 2)
            prefix = b"\n" if ledger.read(1) not in (b"", b"\n") else b""
            ledger.write(prefix + (json.dumps(row) + "\n").encode("utf-8"))


def main(argv):
    if windows_wrapper := argv[:1] == ["--windows-wrapper"]:
        argv = argv[1:]
    ledger = user_path("CONFLUX_LEDGER", ".local/state/conflux/ledger.jsonl") if windows_wrapper and argv[:1] in (["usage"], ["dispatch"]) else None
    if argv[:1] == ["usage"]:
        return usage(argv[1:], ledger, windows_wrapper)
    if argv[:1] == ["handoff"]:
        return handoff(argv[1:])
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("command", choices=("dispatch",))
    parser.add_argument("--policy", required=not (windows_wrapper and argv[:1] == ["dispatch"]), type=Path)
    for field in ROUTE_KEY:
        parser.add_argument(f"--{field}", required=True)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--authorize-paid", default="")
    parser.add_argument("--orca-bin", default="orca")
    parser.add_argument("--ledger", type=Path, default=ledger)
    parser.add_argument("--now")

    separator = argv.index("--") if "--" in argv else len(argv)
    args = parser.parse_args(argv[:separator])
    if args.agent == "antigravity" and args.ledger is None:
        parser.error("antigravity requires --ledger")
    try:
        routes = load_routes(args.policy or user_path("CONFLUX_POLICY", ".config/conflux/policy.json"))
    except (OSError, ValueError) as error:
        parser.error(f"cannot load policy: {error}")
    route = routes.get((args.agent, args.profile, args.model))
    if route is None:
        parser.error("unknown policy route")
    if route["billing"] == "paid" and not args.authorize_paid.strip():
        parser.error("paid route requires --authorize-paid with a nonblank reason")
    if not args.cwd.is_dir():
        parser.error("--cwd must be an existing directory")
    for token in (native := argv[separator + 1:]):
        if (flag := token.partition("=")[0]) in BLOCKED:
            parser.error(f"Orca arguments cannot override {flag}")

    ledger = args.ledger.resolve() if args.ledger is not None else None
    if args.agent == "antigravity":
        try:
            if not window(ledger, utc(args.now))["agy_allowed_next"]:
                parser.error("antigravity exceeds the 5-hour dispatch ratio")
        except DATA_ERRORS as error:
            parser.error(f"cannot read ledger: {error}")
    binary = str(Path(args.orca_bin).absolute()) if os.path.dirname(args.orca_bin) else args.orca_bin
    command = [binary, "orchestration", "worker-start", "--agent", args.agent, *([] if args.model == "default" else ["--model", args.model]), *native]
    command += ["--keep-open"] if route["keep_open_default"] and "--keep-open" not in native else []
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
                append_receipt(ledger, result.stdout, utc(args.now), route)
            except DATA_ERRORS as error:
                print(f"cannot append ledger: {error}", file=sys.stderr)
    return result.returncode if result.returncode >= 0 else 128 - result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
