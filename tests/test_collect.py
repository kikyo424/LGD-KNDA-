import sqlite3
import unittest
from unittest.mock import patch
from collector.collect import normalize, save_items, request_items

class CollectorTests(unittest.TestCase):
    def test_normalization_and_conditions(self):
        item = normalize({'title': ['High brightness tandem OLED'], 'DOI': '10.1/ABC',
                          'published': {'date-parts': [[2025, 3]]}})
        self.assertEqual(item['id'], '10.1/abc')
        self.assertEqual(item['published'], '2025-03')
        self.assertIn('탠덤 OLED', item['tags'])
        self.assertEqual(item['measurement'], '측정 수치·조건 미추출')

    def test_unrelated_and_unsafe_items_rejected(self):
        self.assertIsNone(normalize({'title': ['Battery market'], 'URL': 'https://example.org'}))
        self.assertIsNone(normalize({'title': ['OLED'], 'URL': 'javascript:alert(1)'}))

    def test_idempotent_storage(self):
        item = normalize({'title': ['OLED display'], 'DOI': '10.1/test'})
        with sqlite3.connect(':memory:') as db:
            self.assertEqual(save_items(db, [item, item]), 1)
            self.assertEqual(save_items(db, [item]), 0)
            self.assertEqual(db.execute('SELECT count(*) FROM articles').fetchone()[0], 1)

    @patch('collector.collect.time.sleep')
    @patch('collector.collect.urlopen', side_effect=TimeoutError('timeout'))
    def test_network_retry_is_bounded(self, opener, sleeper):
        with self.assertRaises(TimeoutError):
            request_items('OLED', 1)
        self.assertEqual(opener.call_count, 3)

class PipelineTests(unittest.TestCase):
    def run_pipeline(self, responses):
        import json
        import sys
        import tempfile
        from pathlib import Path
        from collector.collect import main
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'db.sqlite'
            output = Path(directory) / 'out.json'
            existing = normalize({'title': ['Existing OLED'], 'DOI': '10.1/existing'})
            with sqlite3.connect(db) as connection:
                save_items(connection, [existing])
            with patch.object(sys, 'argv', ['collect', '--db', str(db), '--output', str(output)]), \
                 patch('collector.collect.request_items', side_effect=responses), \
                 patch('collector.collect.time.sleep'):
                failure = None
                try:
                    main()
                except SystemExit as exc:
                    failure = exc
            return json.loads(output.read_text()), failure

    def test_partial_failure_continues_and_preserves_existing(self):
        payload, failure = self.run_pipeline([TimeoutError('offline'),
            [{'title': ['New OLED'], 'DOI': '10.1/new'}], [], []])
        self.assertIsNone(failure)
        self.assertEqual(len(payload['articles']), 2)
        self.assertFalse(payload['reports'][0]['ok'])
        self.assertTrue(payload['reports'][1]['ok'])

    def test_total_failure_has_nonzero_outcome_and_preserves_existing(self):
        payload, failure = self.run_pipeline([TimeoutError('offline')] * 4)
        self.assertIsNotNone(failure)
        self.assertEqual(len(payload['articles']), 1)
