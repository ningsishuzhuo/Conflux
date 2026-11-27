import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys


DATA_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError)


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
    dispatches = {row["dispatch_id"]: row for row in ledger_rows(path)
                  if start < utc(row["ts"]) <= now}
    counts = Counter(row["agent"] for row in dispatches.values())
    agy, codex = counts["antigravity"], counts["codex"]
    return dict(window_hours=5, agy_calls=agy, codex_calls=codex,
                other_calls=len(dispatches) - agy - codex,
                paid_calls=sum(row.get("billing") == "paid" for row in dispatches.values()),
                total_dispatches=len(dispatches),
                agy_allowed_next=2 * (agy + 1) < codex,
                metric_kind="conflux_dispatch_proxy")


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


def user_path(variable, suffix):
    return Path(os.environ.get(variable) or Path(os.environ["USERPROFILE"]) / suffix)


def agy_coordinator(brain_dir, now, prune_old):
    start = now - timedelta(hours=5)
    fields = ("input_tokens", "cache_read_tokens", "output_tokens")
    result = dict.fromkeys(("sessions", "turns", *fields, "total_tokens",
                            "max_turn_context_tokens"), 0)
    for path in brain_dir.glob("*/.system_generated/logs/transcript.jsonl"):
        latest = None
        try:
            if prune_old and path.stat().st_mtime < start.timestamp():
                continue
            source = path.open("rb")
        except FileNotFoundError:
            continue
        with source:
            for line in source:
                try:
                    row = json.loads(line)
                    if row.get("type") != "PLANNER_RESPONSE":
                        continue
                    created_at = row.get("created_at")
                    if not isinstance(created_at, str):
                        continue
                    stamp = utc(created_at)
                except (ValueError, AttributeError, OverflowError):
                    continue
                if not start < stamp <= now:
                    continue
                tokens = [row.get(field, 0) for field in fields]
                tokens = [value if type(value) is int and value >= 0 else 0
                          for value in tokens]
                result["turns"] += 1
                for field, value in zip(fields, tokens):
                    result[field] += value
                if latest is None or stamp >= latest:
                    latest = stamp
                    context = tokens[0] + tokens[1]
        if latest is not None:
            result["sessions"] += 1
            result["max_turn_context_tokens"] = max(result["max_turn_context_tokens"], context)
    result["total_tokens"] = sum(result[field] for field in fields)
    return result


def usage(argv, ledger=None, windows_wrapper=False):
    parser = argparse.ArgumentParser(prog="conflux.py usage", allow_abbrev=False)
    parser.add_argument("--ledger", required=ledger is None, default=ledger, type=Path)
    parser.add_argument("--codex-jsonl", action="append", type=Path, default=[])
    parser.add_argument("--agy-brain-dir", type=Path, default=None)
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    try:
        now = utc(args.now)
        result = window(args.ledger, now)
        brain_dir = args.agy_brain_dir
        if windows_wrapper and brain_dir is None:
            candidate = user_path("CONFLUX_AGY_BRAIN_DIR", ".gemini/antigravity-cli/brain")
            if candidate.is_dir():
                brain_dir = candidate
        if brain_dir is not None:
            result["agy_coordinator"] = agy_coordinator(brain_dir, now, args.now is None)
        if args.codex_jsonl:
            paths = dict.fromkeys(path.resolve() for path in args.codex_jsonl)
            result["codex_tokens"] = [codex_tokens(path, now) for path in paths]
    except DATA_ERRORS as error:
        parser.error(f"cannot read usage: {error}")
    print(json.dumps(result))
    return 0
