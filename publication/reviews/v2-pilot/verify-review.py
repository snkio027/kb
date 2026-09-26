#!/usr/bin/env python3
"""Repeatable, read-only verification of the exported review subset."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def main():
    artifact_count = page_count = input_count = 0
    inventory = load(HERE / 'inventory.json')
    for product in inventory:
        folder = HERE / product['profile']
        export = load(folder / 'export.json')
        for entry in export['exported']:
            raw = (folder / entry['path']).read_bytes()
            assert sha(raw) == entry['sha256'] and len(raw) == entry['bytes'], entry['path']
        ready = load(folder / 'preview-result.json')
        assert ready['status'] == 'PREVIEW_READY'
        assert sha((folder / 'preview-audit.json').read_bytes()) == ready['audit_sha256']
        manifest = load(folder / 'candidate-manifest.json')
        terminal = load(folder / 'candidate-result.json')
        assert sha((folder / 'candidate-manifest.json').read_bytes()) == terminal['manifest_sha256']
        model = manifest['identity']['publication']
        assert model == load(folder / 'run.json')['identity']['publication']
        assert model['profile'] == product['profile']
        assert sorted(model['views']) == sorted(a['view'] for a in product['artifacts'])
        for source in model['sources']:
            expected = subprocess.check_output(['git', 'cat-file', 'blob', source['commit'] + ':' + source['path']], cwd=ROOT)
            assert expected == (folder / 'output/source' / source['path']).read_bytes()
            assert sha(expected) == source['sha256']
            if product['profile'] == 'cpp-handbook':
                assert source['commit'] == source['revision'] == '8f479deaf660533b2ad82e1f721eb41a363112b6'
        for item in load(folder / 'run.json')['identity']['inputs']:
            if not item['path'].startswith(('sources/', 'source-set.json')):
                assert sha((ROOT / item['path']).read_bytes()) == item['sha256'], item['path']
                input_count += 1
        for artifact in product['artifacts']:
            pdf = HERE / artifact['path']
            assert sha(pdf.read_bytes()) == artifact['sha256'] == ready['artifacts']['output/pdf/' + pdf.name]
            reader = PdfReader(pdf)
            assert len(reader.pages) == artifact['pages'] and reader.outline
            page_count += len(reader.pages)
            artifact_count += 1
    assert artifact_count == 10 and page_count == 678
    # Check only maintained publication navigation, not immutable raw source attachments.
    link_count = 0
    for path in (ROOT / 'publication/README.md', HERE / 'README.md', ROOT / 'design/README.md'):
        ast = json.loads(subprocess.check_output(['pandoc', str(path), '-f', 'gfm', '-t', 'json']))
        for node in walk(ast):
            if node.get('t') != 'Link':
                continue
            target = urlsplit(node['c'][2][0])
            if target.scheme or target.netloc or not target.path:
                continue
            assert (path.parent / unquote(target.path)).exists(), (path, target.path)
            link_count += 1
    suspicious = re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}')
    for path in (ROOT / 'publication').rglob('*'):
        if not path.is_file() or 'build' in path.relative_to(ROOT / 'publication').parts:
            continue
        if path.suffix == '.json':
            load(path)
        if path.suffix not in ('.pdf', '.png'):
            assert not suspicious.search(path.read_bytes()), 'Potential credential: ' + str(path)
    print(json.dumps({'review_artifacts': artifact_count, 'pages': page_count,
                      'current_implementation_input_bindings_checked': input_count,
                      'maintained_markdown_files_parsed': 3, 'local_file_links_checked': link_count,
                      'export_hashes': 'MATCH', 'source_revisions_and_paths': 'MATCH',
                      'json_parse': 'PASS', 'targeted_credential_patterns': 'NONE_FOUND',
                      'limits': 'File links only; no external URL, all-anchor or comprehensive secret-scan claim.'}, indent=2))


if __name__ == '__main__':
    main()
