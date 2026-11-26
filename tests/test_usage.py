import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_dispatch import fake_orca


CLI = Path(__file__).resolve().parents[1] / "conflux.py"
NOW = "2026-11-26T10:00:00Z"
EDGE = "2026-11-26T05:00:00Z"


class UsageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.ledger = self.root / "ledger"
        self.policy = self.root / "policy"
        self.policy.write_text(json.dumps({"routes": [
            dict(agent=agent, profile="p", model="m", billing="subscription",
                 keep_open_default=False)
            for agent in ("codex", "antigravity", "dsh", "claude")
        ]}), encoding="utf-8")
        self.orca = fake_orca(self.root / "orca", """import json, os, sys
receipt = bytes.fromhex(sys.argv[7]).decode("utf-8")
if json.loads(receipt).get("dispatchId") == "c3" and os.path.isfile("ledger.lock"):
    with open("ledger.lock", "a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
print(receipt, end="")
print("orca stderr", end="", file=sys.stderr)
sys.exit(int(sys.argv[8]))
""")

    def run_cli(self, command, *args):
        return subprocess.run(
            [sys.executable, str(CLI), command, "--ledger", str(self.ledger),
             "--now", NOW, *args], capture_output=True, text=True
        )

    def dispatch(self, agent, dispatch_id="", status=0, *, nested=False):
        receipt = {"dispatchId": dispatch_id}
        if nested:
            receipt = {"result": receipt}
        return self.run_cli(
            "dispatch", "--policy", str(self.policy), "--agent", agent,
            "--profile", "p", "--model", "m", "--cwd", str(self.root),
            "--orca-bin", str(self.orca), "--", json.dumps(receipt).encode("utf-8").hex(), str(status)
        )

    def rows(self):
        return [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]

    def usage(self, *args):
        result = self.run_cli("usage", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_antigravity_requires_ledger_before_calling_orca(self):
        result = subprocess.run(
            [sys.executable, str(CLI), "dispatch", "--policy", str(self.policy),
             "--agent", "antigravity", "--profile", "p", "--model", "m",
             "--cwd", str(self.root), "--orca-bin", str(self.orca),
             "--", '{"dispatchId": "a1"}', "0"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("antigravity requires --ledger", result.stderr)
        self.assertNotIn("orca stderr", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_window_boundaries_and_duplicate_ids(self):
        rows = [
            (EDGE, "edge"), ("2026-11-26T05:00:00.000001Z", "inside"),
            (NOW, "now"), (NOW, "now"), ("2026-11-26T10:00:01Z", "future"),
        ]
        self.ledger.write_text("".join(json.dumps(dict(ts=ts, dispatch_id=key,
                                                       agent="codex")) + "\n"
                                       for ts, key in rows), encoding="utf-8")
        before = self.ledger.read_bytes()
        self.assertEqual(self.usage(), dict(window_hours=5, codex_calls=2,
                         agy_calls=0, other_calls=0, agy_allowed_next=False,
                         metric_kind="conflux_dispatch_proxy"))
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertFalse((self.root / "ledger.lock").exists())

    def test_strict_ratio_and_other_agents(self):
        self.assertEqual(self.dispatch("antigravity", "a").returncode, 2)
        self.assertFalse(self.ledger.exists())
        for agent, key in [("codex", "c1"), ("codex", "c2"), ("dsh", "d"),
                           ("claude", "cl")]:
            self.assertEqual(self.dispatch(agent, key).returncode, 0)
        denied = self.dispatch("antigravity", "a")
        self.assertEqual(denied.returncode, 2)
        self.assertNotIn("orca stderr", denied.stderr)
        self.assertEqual(self.dispatch("codex", "c3").returncode, 0)
        self.assertTrue(self.usage()["agy_allowed_next"])
        self.assertEqual(self.dispatch("antigravity", "a").returncode, 0)
        self.assertEqual(self.dispatch("antigravity", "a2").returncode, 2)
        result = self.usage()
        self.assertEqual((result["agy_calls"], result["codex_calls"],
                          result["other_calls"]), (1, 3, 2))

    def test_receipts_and_passthrough(self):
        failed = self.dispatch("codex", "failed", 7)
        self.assertEqual((failed.returncode, failed.stderr), (7, "orca stderr"))
        self.assertEqual(json.loads(failed.stdout), {"dispatchId": "failed"})
        no_id = self.dispatch("codex", "   ")
        self.assertEqual(no_id.returncode, 0)
        self.assertIn("dispatchId", no_id.stderr)
        self.assertFalse(self.ledger.exists())
        self.assertEqual(self.dispatch("codex", "id", nested=True).returncode, 0)
        self.assertEqual(self.dispatch("codex", "id").returncode, 0)
        self.assertEqual(self.rows(), [dict(ts=NOW, dispatch_id="id", agent="codex",
                                           profile="p", model="m", billing="subscription")])

    def test_concurrent_append(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: self.dispatch("codex", str(i % 8)),
                                    range(24)))
        self.assertTrue(all(result.returncode == 0 for result in results))
        self.assertCountEqual([row["dispatch_id"] for row in self.rows()],
                              map(str, range(8)))

    def token_evidence(self, rows, earlier=()):
        log = self.root / "codex.jsonl"
        events = [dict(timestamp=ts, type="event_msg", payload=dict(
            type="token_count", info={field: dict(total_tokens=value)}))
            for ts, field, value in rows]
        log.write_text("".join(json.dumps(event) + "\n" for event in [*earlier, *events]), encoding="utf-8")
        return self.usage("--codex-jsonl", str(log), "--codex-jsonl", str(log))[
            "codex_tokens"]

    def test_token_baseline_and_duplicate_counters(self):
        total = "total_token_usage"
        self.assertEqual(self.token_evidence([
            ("2026-11-26T04:59:00Z", total, 90), (EDGE, total, 100),
            (NOW, total, 125), (NOW, total, 125),
            ("2026-11-26T10:00:01Z", total, 140),
        ]), [dict(path=str(self.root / "codex.jsonl"), status="ok", total_tokens=25)])
        self.assertFalse(self.ledger.exists())

    def test_missing_token_baseline(self):
        evidence, = self.token_evidence(
            [(NOW, "total_token_usage", 25)],
            earlier=[dict(timestamp=EDGE, type="session_meta")],
        )
        self.assertEqual(evidence["status"], "missing_baseline")
        self.assertNotIn("total_tokens", evidence)

    def test_token_counter_reset(self):
        evidence, = self.token_evidence([
            (EDGE, "total_token_usage", 100), (NOW, "total_token_usage", 12)
        ])
        self.assertEqual(evidence["status"], "counter_reset")
        self.assertNotIn("total_tokens", evidence)

    def test_explicit_token_increment(self):
        evidence, = self.token_evidence([
            (NOW, "last_token_usage", 12), (NOW, "last_token_usage", 12)
        ])
        self.assertEqual((evidence["status"], evidence["total_tokens"]), ("ok", 12))

    def test_new_session_uses_zero_baseline(self):
        total = "total_token_usage"
        evidence, = self.token_evidence([(NOW, total, 25)])
        self.assertEqual((evidence["status"], evidence["total_tokens"]), ("ok", 25))

    def test_only_antigravity_prechecks_malformed_ledger(self):
        self.ledger.write_text("[]\n", encoding="utf-8")
        for agent in ("codex", "dsh", "claude"):
            result = self.dispatch(agent, agent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("orca stderr", result.stderr)
        result = self.dispatch("antigravity", "agy")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("orca stderr", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_damaged_ledger_line_does_not_block_appends(self):
        self.ledger.write_bytes(b'{"dispatch_id":')
        result = self.dispatch("codex", "first")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipping damaged ledger line", result.stderr)
        self.assertEqual(self.dispatch("codex", "second").returncode, 0)
        self.assertEqual(self.usage()["codex_calls"], 2)

    def test_invalid_usage_shapes_are_cli_errors(self):
        self.ledger.write_text("[]\n", encoding="utf-8")
        result = self.run_cli("usage")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.ledger.unlink()
        log = self.root / "codex.jsonl"
        for row in ([], dict(timestamp=NOW, payload=[]),
                    dict(timestamp=NOW, type="token_count", info=[]),
                    dict(timestamp=NOW, type="token_count", total_token_usage=[])):
            with self.subTest(row=row):
                log.write_text(json.dumps(row) + "\n", encoding="utf-8")
                result = self.run_cli("usage", "--codex-jsonl", str(log))
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)
