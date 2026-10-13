"""Release gates reject stale/private outputs and changed original evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_beta import validate

SITE = Path(__file__).resolve().parents[1] / 'docs' / 'beta'


class BetaArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='exchange-artifact-tests-')
        self.site = Path(self.temporary.name) / 'beta'
        shutil.copytree(SITE, self.site)

    def tearDown(self):
        self.temporary.cleanup()

    def update_manifest(self, relative):
        path = self.site / 'build-manifest.json'
        manifest = json.loads(path.read_text('utf-8'))
        manifest['files'][relative] = hashlib.sha256((self.site / relative).read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest), encoding='utf-8')

    def test_current_bundle_is_valid(self):
        self.assertEqual(validate(self.site), {'capabilities': 0, 'synthetic_capabilities': 3})

    def test_private_and_stale_files_are_not_publishable(self):
        for name in ('private-wallet.db', 'synthetic/v1/evidence/withdrawn.json'):
            with self.subTest(name=name):
                extra = self.site / name
                extra.parent.mkdir(parents=True, exist_ok=True)
                extra.write_text('{}', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'unexpected, private or stale'):
                    validate(self.site)
                extra.unlink()

    def test_original_receipt_tampering_fails_even_if_outer_manifest_updated(self):
        relative = 'synthetic/v1/evidence/synthetic-digest-receipt.json'
        (self.site / relative).write_text('{}', encoding='utf-8')
        self.update_manifest(relative)
        with self.assertRaisesRegex(ValueError, 'original public evidence hash mismatch'):
            validate(self.site)

    def test_original_record_tampering_fails(self):
        relative = 'synthetic/v1/submissions/capabilities/text-digest-1.0.0.json'
        (self.site / relative).write_text('{}', encoding='utf-8')
        self.update_manifest(relative)
        with self.assertRaisesRegex(ValueError, 'original public evidence hash mismatch'):
            validate(self.site)

    def test_reviewed_catalog_cannot_promote_synthetic_fixtures(self):
        relative = 'catalog/v1/index.json'
        fake = json.loads((self.site / 'synthetic/v1/index.json').read_text('utf-8'))
        fake['synthetic'] = False
        (self.site / relative).write_text(json.dumps(fake), encoding='utf-8')
        self.update_manifest(relative)
        with self.assertRaisesRegex(ValueError, 'mislabeled'):
            validate(self.site)

    def test_symlinks_are_not_published(self):
        (self.site / 'leak.json').symlink_to(self.site / 'catalog/v1/index.json')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            validate(self.site)

    def test_frozen_losses_cannot_be_removed(self):
        relative = 'economic-validation.json'
        path = self.site / relative
        trial = json.loads(path.read_text('utf-8'))
        trial['scenarios'] = [row for row in trial['scenarios'] if row['scenario'] != 'reversal']
        path.write_text(json.dumps(trial), encoding='utf-8')
        self.update_manifest(relative)
        with self.assertRaisesRegex(ValueError, 'loss or sparse result missing'):
            validate(self.site)


if __name__ == '__main__':
    unittest.main()
