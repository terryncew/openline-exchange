"""Legacy operator ingestion cannot fetch arbitrary URLs or publish from CI."""
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import add_offer


class LegacyOfferSafetyTests(unittest.TestCase):
    def test_unapproved_and_unsafe_urls_never_open_a_connection(self):
        rows = [
            ['--url', 'https://example.invalid/receipt.json'],
            ['--url', 'http://terryncew.github.io/receipt.json', '--allowed-host', 'terryncew.github.io'],
            ['--url', 'https://credential:testsecret@terryncew.github.io/receipt.json', '--allowed-host', 'terryncew.github.io'],
            ['--url', 'https://127.0.0.1/receipt.json', '--allowed-host', '127.0.0.1'],
            ['--url', 'https://terryncew.github.io/receipt.json'],
        ]
        for row in rows:
            with self.subTest(row=row), patch.object(sys, 'argv', ['add_offer.py', *row, '--price', '1', '--royalty', '0']), patch.object(add_offer, 'build_opener') as opener:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(add_offer.main(), 2)
                opener.assert_not_called()
                self.assertNotIn('testsecret', output.getvalue())

    def test_redirect_handler_never_follows_a_receipt_redirect(self):
        self.assertIsNone(add_offer.NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://127.0.0.1/private'))

    def test_manual_workflow_has_no_network_input_or_write_token_or_git_push(self):
        content = (Path(__file__).resolve().parents[1] / '.github/workflows/add-offer.yml').read_text('utf-8')
        self.assertNotIn('receipt_url:', content)
        self.assertIn('contents: read', content)
        self.assertIn('--file docs/receipt.latest.json', content)
        self.assertNotIn('git push', content)


if __name__ == '__main__':
    unittest.main()
