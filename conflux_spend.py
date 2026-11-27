from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import re

def utc(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).astimezone(timezone.utc)

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


def claude_spend(root, config_path, now):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    windows = {}
    for key, limit in config["limits_usd"].items():
        match = re.fullmatch(r"([1-9][0-9]*)([hd])", key)
        if not match:
            raise ValueError(f"invalid window: {key}")
        delta = timedelta(hours=int(match[1]) * (24 if match[2] == "d" else 1))
        windows[key] = (delta, Decimal(str(limit)))
    if not windows:
        raise ValueError("no spend windows")
    records = {}
    for path in root.rglob("*.jsonl"):
        if path.stat().st_mtime < (now - max(delta for delta, _ in windows.values())).timestamp():
            continue
        with path.open(encoding="utf-8") as source:
            lines = source.readlines()
        for index, line in enumerate(lines):
            if '"usage"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                if index == len(lines) - 1 and not line.endswith("\n"):
                    continue
                return {"status": "corrupt", "path": str(path), "line": index + 1}
            message = row.get("message", {})
            if message.get("model") == "<synthetic>" or not message.get("usage"):
                continue
            stamp = utc(row["timestamp"])
            if not (now - max(delta for delta, _ in windows.values()) < stamp <= now):
                continue
            ident = message["id"]
            if ident not in records or message["usage"].get("output_tokens", 0) > records[ident]["message"]["usage"].get("output_tokens", 0):
                records[ident] = row
    totals = {key: Decimal(0) for key in windows}
    fallback = set()
    for row in records.values():
        message = row["message"]
        name = re.sub(r"\[.*\]$", "", row.get("requestedModel") or message["model"])
        channels = [p for p in config["channels"] if name.startswith(p)]
        prefix = max(channels, key=len) if channels else ""
        if not prefix and "--" in name:
            return {"status": "unpriced", "model": name}
        multiplier = Decimal(str(config["channels"][prefix])) if prefix else Decimal(1)
        model = name[len(prefix):]
        cost = Decimal(0)
        if multiplier:
            price = config["models"].get(model)
            if price is None:
                matches = [p for p in config["families"] if p != "*" and model.startswith(p)]
                family = max(matches, key=len) if matches else "*"
                price = config["families"].get(family)
                if price is None:
                    return {"status": "unpriced", "model": model}
                fallback.add(model)
            rates = {key: Decimal(str(price[key])) for key in ("input", "output", "cache_write")}
            rates["cache_read"] = Decimal(str(price["cache_read"])) if "cache_read" in price else rates["input"] * Decimal("0.1")
            usage = message["usage"]
            cost = sum(Decimal(str(usage.get(field, 0))) * rates[rate] for field, rate in (("input_tokens", "input"), ("output_tokens", "output"), ("cache_creation_input_tokens", "cache_write"), ("cache_read_input_tokens", "cache_read"))) * multiplier / Decimal(1000000)
        stamp = utc(row["timestamp"])
        for key, (delta, _) in windows.items():
            if now - delta < stamp <= now:
                totals[key] += cost
    return {"status": "ok", "windows": {key: {"usd": str(totals[key]), "limit_usd": str(limit), "exceeded": totals[key] >= limit} for key, (_, limit) in windows.items()}, "fallback_models": sorted(fallback)}
