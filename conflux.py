import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


from conflux_handoff import exclusive_lock, handoff
from conflux_spend import codex_tokens, claude_spend


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
    stamp = datetime.now(timezone.utc) if value is None else datetime.fromisoformat(
        value[:-1] + "+00:00" if value.endswith("Z") else value)
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


def user_path(variable, suffix):
    return Path(os.environ.get(variable) or Path(os.environ["USERPROFILE"]) / suffix)


def spend_options(parser, default=None):
    parser.add_argument("--spend-config", type=Path, default=default)
    parser.add_argument("--claude-projects", type=Path, default=Path.home() / ".claude/projects")


def usage(argv, ledger=None, spend_default=None):
    parser = argparse.ArgumentParser(prog="conflux.py usage", allow_abbrev=False)
    parser.add_argument("--ledger", required=ledger is None, default=ledger, type=Path)
    parser.add_argument("--codex-jsonl", action="append", type=Path, default=[])
    parser.add_argument("--now")
    spend_options(parser, spend_default)
    args = parser.parse_args(argv)
    try:
        now = utc(args.now)
        result = window(args.ledger, now)
        if args.spend_config:
            result["claude_spend"] = claude_spend(args.claude_projects, args.spend_config, now)
        if args.codex_jsonl:
            paths = dict.fromkeys(path.resolve() for path in args.codex_jsonl)
            result["codex_tokens"] = [codex_tokens(path, now) for path in paths]
    except DATA_ERRORS as error:
        parser.error(f"cannot read usage: {error}")
    print(json.dumps(result))
    return 0


def main(argv):
    if windows_wrapper := argv[:1] == ["--windows-wrapper"]:
        argv = argv[1:]
    ledger = user_path("CONFLUX_LEDGER", ".local/state/conflux/ledger.jsonl") if windows_wrapper and argv[:1] in (["usage"], ["dispatch"]) else None
    spend_default = user_path("CONFLUX_SPEND", ".config/conflux/spend.json") if windows_wrapper else None
    spend_default = spend_default if spend_default and spend_default.exists() else None
    if argv[:1] in (["usage"], ["handoff"]):
        return usage(argv[1:], ledger, spend_default) if argv[0] == "usage" else handoff(argv[1:])
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
    spend_options(parser, spend_default)

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
    if route["billing"] == "paid" and args.spend_config:
        try:
            spend = claude_spend(args.claude_projects, args.spend_config, utc(args.now))
            if spend["status"] != "ok" or any(w["exceeded"] for w in spend["windows"].values()):
                parser.error(f"Claude spend guard: {spend}")
            if spend["fallback_models"]:
                print(f"warning: fallback pricing: {spend['fallback_models']}", file=sys.stderr)
        except DATA_ERRORS as error:
            parser.error(f"cannot read Claude spend: {error}")
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
