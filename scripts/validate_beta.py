#!/usr/bin/env python3
"""Fail-closed artifact gates; no capability code or private evidence is executed.

Hashes bind reviewed source bytes and generated files, not maintainer identity or
actual outcomes. Public disclosure and source review are separate release gates.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = ('catalog/v1/index.json', 'synthetic/v1/index.json', 'economic-validation.json')
UI_FILES = ('index.html', 'app.js', 'model.mjs', 'style.css', 'README.md')
MAX_FILE = 2_000_000
SHA = re.compile(r'^[0-9a-f]{64}$')
SCHEMAS = {'capability.schema.json', 'worker.schema.json', 'evaluation.schema.json', 'catalog.schema.json', 'reproduction.schema.json', 'reviews.schema.json'}


def safe_artifact(path):
    if not isinstance(path, str) or not re.fullmatch(r'(?:submissions/(?:capabilities|workers|evaluations)|evidence|reproductions)/[A-Za-z0-9._/-]+\.json', path) or any(part in ('', '.', '..') for part in path.split('/')):
        raise ValueError('unsupported public artifact path')
    return path


def load(site, relative):
    path = site / relative
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError('missing, symlinked or oversized beta artifact')
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(path.read_text('utf-8'), object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite JSON')))


def artifact_references(catalog, prefix):
    references = {}
    for kind in ('capabilities', 'workers', 'evaluations'):
        for row in catalog[kind]:
            if row.get('record_url'):
                references[f"{prefix}/{safe_artifact(row['record_url'])}"] = row['record_sha256']
            for evidence in row.get('evidence', []):
                path = evidence.get('source_url') or evidence.get('path')
                references[f"{prefix}/{safe_artifact(path)}"] = evidence['sha256']
            reproduction = row.get('reproduction')
            if reproduction:
                path = reproduction.get('source_url')
                references[f"{prefix}/{safe_artifact(path)}"] = reproduction.get('sha256') or reproduction.get('report_sha256')
    return references


def validate(site):
    manifest = load(site, 'build-manifest.json')
    if manifest.get('format') != 'openline.exchange.beta-build.v1' or not isinstance(manifest.get('files'), dict):
        raise ValueError('unsupported build manifest')
    for field in ('compiler_sha256', 'trial_verifier_sha256'):
        if not SHA.fullmatch(manifest.get(field, '')):
            raise ValueError('compiler identity hash missing')
    expected = set(DATA_FILES) | set(UI_FILES)
    for relative, synthetic in (('catalog/v1/index.json', False), ('synthetic/v1/index.json', True)):
        catalog = load(site, relative)
        if catalog.get('format') != 'openline.catalog.v1' or catalog.get('synthetic') is not synthetic:
            raise ValueError('catalog format or synthetic boundary mismatch')
        for key in ('capabilities', 'workers', 'evaluations'):
            rows = catalog.get(key)
            if not isinstance(rows, list) or len(rows) > 500:
                raise ValueError('unsupported catalog collection')
            for row in rows:
                if row.get('synthetic') is not synthetic or row.get('publication', {}).get('reviewed') is not True or not SHA.fullmatch(row.get('record_sha256', '')):
                    raise ValueError('catalog contains unreviewed, mislabeled or unhashed record')
                if synthetic and row.get('inquiry', {}).get('accepts_inquiries'):
                    raise ValueError('synthetic inquiry publication prohibited')
                if row.get('inquiry', {}).get('accepts_inquiries'):
                    u = urlsplit(row.get('inquiry', {}).get('url', ''))
                    if (u.scheme, u.netloc, u.path, u.query, u.fragment) != ('https', 'github.com', '/terryncew/openline-bureau/issues/new', '', ''):
                        raise ValueError('unapproved inquiry destination')
        for c in catalog['capabilities']:
            if synthetic != (c.get('evidence_summary', {}).get('label') == 'SYNTHETIC'):
                raise ValueError('synthetic evidence mislabeled')
        if synthetic and catalog.get('policy', {}).get('inquiries_enabled'):
            raise ValueError('synthetic catalog accepts inquiries')
        if not synthetic and not catalog.get('policy', {}).get('inquiries_enabled') and any(row.get('inquiry', {}).get('accepts_inquiries') for row in catalog['capabilities'] + catalog['workers']):
            raise ValueError('catalog inquiry policy not enabled')
        prefix = str(PurePosixPath(relative).parent)
        for path, expected_hash in artifact_references(catalog, prefix).items():
            load(site, path)
            if not SHA.fullmatch(expected_hash or '') or hashlib.sha256((site / path).read_bytes()).hexdigest() != expected_hash:
                raise ValueError('original public evidence hash mismatch')
            expected.add(path)
        local_references = artifact_references(catalog, prefix)
        schema_dir = site / prefix / 'schemas'
        if not schema_dir.is_dir() or {path.name for path in schema_dir.iterdir()} != SCHEMAS:
            raise ValueError('machine-readable schemas missing or unexpected')
        if schema_dir.exists():
            for path in schema_dir.iterdir():
                if path.name not in SCHEMAS:
                    raise ValueError('unexpected schema artifact')
                load(site, str(path.relative_to(site)))
                relative_schema = str(path.relative_to(site))
                expected.add(relative_schema)
                local_references[relative_schema] = hashlib.sha256(path.read_bytes()).hexdigest()
        ledger_path = prefix + '/artifacts.json'
        ledger = load(site, ledger_path)
        if ledger.get('format') != 'openline.catalog.artifacts.v1' or ledger.get('catalog') != {'path': 'index.json', 'sha256': hashlib.sha256((site / relative).read_bytes()).hexdigest()}:
            raise ValueError('catalog artifact ledger mismatch')
        listed = {prefix + '/' + row['path']: row['sha256'] for row in ledger.get('artifacts', [])}
        if listed != local_references or len(listed) != len(ledger.get('artifacts', [])):
            raise ValueError('catalog ledger contains missing or unrelated public artifacts')
        expected.add(ledger_path)
    if set(manifest['files']) != expected:
        raise ValueError('build manifest contains missing or unreferenced artifacts')
    actual = set()
    for path in site.rglob('*'):
        if path.is_symlink():
            raise ValueError('symlink in public bundle')
        if path.is_file():
            actual.add(str(path.relative_to(site)))
    if actual != expected | {'build-manifest.json'}:
        raise ValueError('unexpected, private or stale file in public bundle')
    for relative in expected:
        if not SHA.fullmatch(manifest['files'].get(relative, '')) or (site / relative).stat().st_size > MAX_FILE or manifest['files'][relative] != hashlib.sha256((site / relative).read_bytes()).hexdigest():
            raise ValueError('generated artifact hash mismatch; rebuild reviewed Bureau source')
    trial = load(site, 'economic-validation.json')
    if trial.get('format') != 'openline.bureau.economic-validation.v1' or trial.get('synthetic') is not True:
        raise ValueError('frozen trial must remain explicitly synthetic')
    scenarios = {row.get('scenario'): row for row in trial.get('scenarios', [])}
    if set(scenarios) != {'mixed', 'reversal', 'sparse'} or scenarios['reversal'].get('completion_delta', 0) >= 0 or scenarios['sparse'].get('verdict') != 'INCONCLUSIVE':
        raise ValueError('frozen trial loss or sparse result missing')
    for filename in ('app.js', 'model.mjs'):
        content = (site / filename).read_text('utf-8')
        if re.search(r'\.(?:innerHTML|outerHTML)\s*=|\beval\s*\(|new\s+Function\s*\(', content):
            raise ValueError('unsafe contributed text rendering')
    return {'capabilities': len(load(site, 'catalog/v1/index.json')['capabilities']), 'synthetic_capabilities': len(load(site, 'synthetic/v1/index.json')['capabilities'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ROOT / 'docs' / 'beta')
    args = parser.parse_args()
    try:
        counts = validate(args.site.resolve())
    except (ValueError, OSError, KeyError, TypeError):
        print('Beta validation failed; inspect reviewed source and rebuild artifacts.', file=sys.stderr)
        return 2
    print(f"Beta artifact gates passed: {counts['capabilities']} reviewed, {counts['synthetic_capabilities']} explicitly synthetic capabilities")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
