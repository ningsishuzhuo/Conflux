import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from conflux_spend import claude_spend


class SpendTests(unittest.TestCase):
    def test_dedup_windows_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'config.json'
            config.write_text(json.dumps({'limits_usd': {'5h': '1', '24h': '10'}, 'channels': {'relay--': '0.1'}, 'models': {}, 'families': {'claude-': {'input': '2', 'output': '10', 'cache_write': '4'}}}))
            now = datetime.now(timezone.utc)
            def row(output):
                return {'timestamp': now.isoformat(), 'requestedModel': 'relay--claude-test[x]', 'message': {'id': 'same', 'model': 'claude-test', 'usage': {'input_tokens': 1000000, 'output_tokens': output}}}
            (root / 'data.jsonl').write_text('\n'.join(json.dumps(row(n)) for n in (1, 1000000)) + '\n')
            result = claude_spend(root, config, now)
            self.assertEqual(float(result['windows']['5h']['usd']), 1.2)
            self.assertTrue(result['windows']['5h']['exceeded'])
            self.assertEqual(result['fallback_models'], ['claude-test'])

    def test_unpriced_and_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'config.json'
            config.write_text(json.dumps({'limits_usd': {'5h': '1'}, 'channels': {}, 'models': {}, 'families': {}}))
            now = datetime.now(timezone.utc)
            data = root / 'a.jsonl'
            data.write_text(json.dumps({'timestamp': now.isoformat(), 'requestedModel': 'unknown--x', 'message': {'id': 'x', 'model': 'x', 'usage': {'output_tokens': 1}}}) + '\n')
            self.assertEqual(claude_spend(root, config, now)['status'], 'unpriced')
            data.write_text('{"usage": broken}\n{}\n')
            self.assertEqual(claude_spend(root, config, now)['status'], 'corrupt')
