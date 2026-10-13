#!/usr/bin/env python3
"""Build reviewed data through an explicitly supplied trusted Bureau checkout.

This operator command executes the reviewed Bureau compiler, never contributed
capability code. Do not run against an unreviewed checkout from a submission.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil

from validate_beta import DATA_FILES, UI_FILES, artifact_references

ROOT = Path(__file__).resolve().parents[1]
GENERATED_PREFIXES = ('catalog/v1/', 'synthetic/v1/')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bureau', type=Path, required=True, help='Trusted, reviewed Bureau checkout')
    parser.add_argument('--out', type=Path, default=ROOT / 'docs' / 'beta')
    args = parser.parse_args()
    bureau = args.bureau.resolve()
    output = args.out.resolve()
    if not (bureau / 'bureau' / 'catalog.py').is_file():
        parser.error('Expected a trusted Bureau checkout with bureau/catalog.py')
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(bureau)
    output.mkdir(parents=True, exist_ok=True)
    for name in UI_FILES:
        if not (output / name).exists():
            shutil.copyfile(ROOT / 'docs' / 'beta' / name, output / name)
    temporary = tempfile.TemporaryDirectory(prefix='openline-beta-build-')
    generated = Path(temporary.name)
    for relative, fixtures in (('catalog/v1', False), ('synthetic/v1', True)):
        destination = generated / relative
        command = [sys.executable, '-m', 'bureau.catalog', 'build', '--source', str(bureau / 'catalog'), '--out', str(destination / 'index.json')]
        if fixtures:
            command.append('--fixtures')
        subprocess.run(command, cwd=bureau, env=environment, check=True)
    subprocess.run([sys.executable, '-m', 'bureau.beta_trial', '--out', str(generated / 'economic-validation.json')], cwd=bureau, env=environment, check=True)
    # Only prune files previously managed by the manifest or existing catalogs.
    previous = set()
    old_manifest = output / 'build-manifest.json'
    if old_manifest.exists():
        previous.update(json.loads(old_manifest.read_text('utf-8')).get('files', {}))
    for relative in ('catalog/v1/index.json', 'synthetic/v1/index.json'):
        old_catalog = output / relative
        if old_catalog.is_file():
            previous.update(artifact_references(json.loads(old_catalog.read_text('utf-8')), str(Path(relative).parent)))
    new_files = {str(path.relative_to(generated)) for path in generated.rglob('*') if path.is_file()}
    for relative in previous - new_files:
        if relative.startswith(GENERATED_PREFIXES) and '..' not in Path(relative).parts and not Path(relative).is_absolute():
            old = output / relative
            if old.is_symlink():
                raise ValueError('refusing symlink in previously managed outputs')
            if old.is_file():
                old.unlink()
    for relative in new_files:
        target = output / relative
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
            raise ValueError('refusing symlink output')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(generated / relative, target)
    temporary.cleanup()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=bureau, text=True).strip()
    manifest = {'format': 'openline.exchange.beta-build.v1', 'bureau_revision': revision,
                'compiler_sha256': digest(bureau / 'bureau' / 'catalog.py'),
                'trial_verifier_sha256': digest(bureau / 'bureau' / 'beta_trial.py'),
                'files': {relative: digest(output / relative) for relative in sorted(new_files | set(UI_FILES))},
                'notice': 'Hashes bind generated files, not maintainer identity or task outcomes. A deployment needs review of the Bureau source and publication registry.'}
    (output / 'build-manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'validate_beta.py'), '--site', str(output)], check=True)


if __name__ == '__main__':
    main()
