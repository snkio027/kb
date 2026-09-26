#!/usr/bin/env python3
"""Copy a declared subset of two frozen candidates for Git review, without rebuilding."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = '8f479deaf660533b2ad82e1f721eb41a363112b6'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(folder):
    manifest_raw = (folder / 'candidate-manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    terminal = json.loads((folder / 'candidate-result.json').read_bytes())
    assert terminal['status'] == 'CANDIDATE_PREPARED_FOR_REVIEW'
    assert terminal['manifest_sha256'] == sha(manifest_raw)
    identity = manifest['identity']
    assert sha(json.dumps(identity, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()) == manifest['candidate_id']
    model = identity['publication']
    profile = model['profile']
    assert profile in ('esd', 'cpp-handbook')
    audit = json.loads((folder / 'preview-audit.json').read_bytes())
    assert sorted(model['views']) == sorted(v['view'] for v in audit['views'])
    source_checks = []
    for source in model['sources']:
        attached = (folder / 'output/source' / source['path']).read_bytes()
        prepared = (folder / 'inputs' / source['snapshot_path']).read_bytes()
        assert attached == prepared and sha(prepared) == source['sha256']
        committed = subprocess.check_output(['git', 'cat-file', 'blob', source['commit'] + ':' + source['path']], cwd=ROOT)
        assert committed == prepared
        if profile == 'cpp-handbook':
            assert source['commit'] == source['revision'] == FROZEN
            assert source['path'] in ('c++/g06-memory-and-performance.md', 'c++/g07-concurrency-and-memory-model.md')
        source_checks.append({'path': source['path'], 'revision': source['revision'], 'commit': source['commit'],
                              'sha256': sha(prepared), 'bytes': len(prepared), 'git_prepared_attached_equal': True})
    selected = {'run.json', 'result.json', 'preview-result.json', 'preview-audit.json',
                'reading-review.json', 'evidence/source-catalog.json'}
    selected.update(f['path'] for f in identity['files'] if f['path'].startswith('output/') or
                    (f['path'].startswith('evidence/typeset/') and Path(f['path']).name in
                     ('table-map.json', 'reference-map.json', 'section-audit.json', 'audit.json')))
    # Check the complete candidate before exporting only its declared review subset.
    for entry in identity['files']:
        raw = (folder / entry['path']).read_bytes()
        assert len(raw) == entry['bytes'] and sha(raw) == entry['sha256']
    selected.update(('candidate-manifest.json', 'candidate-result.json'))
    destination = HERE / profile
    destination.mkdir(exist_ok=False)
    exported = []
    for name in sorted(selected):
        raw = (folder / name).read_bytes()
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        exported.append({'path': name, 'sha256': sha(raw), 'bytes': len(raw)})
    record = {'role': 'REVIEW_EXPORT_NOT_RELEASE_NOT_COMPLETE_CANDIDATE',
              'candidate': str(folder.relative_to(ROOT)), 'candidate_id': manifest['candidate_id'],
              'all_candidate_file_hashes_verified': True, 'source_checks': source_checks,
              'exported': exported, 'omitted': sorted(f['path'] for f in identity['files'] if f['path'] not in selected)}
    (destination / 'export.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return {'profile': profile, 'candidate_id': manifest['candidate_id'], 'sources': source_checks,
            'artifacts': [{'view': v['view'], 'path': profile + '/' + v['pdf'], 'pages': v['pages'],
                           'sha256': v['sha256']} for v in audit['views']]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidates', nargs=2, type=Path)
    args = parser.parse_args()
    inventory = [capture(path.resolve()) for path in args.candidates]
    with (HERE / 'inventory.json').open('x') as stream:
        stream.write(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(inventory, ensure_ascii=False, indent=2))
