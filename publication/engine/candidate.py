"""Freeze an existing checked PREVIEW for review; never compile or publish."""
import json
import os
import re
import stat
import uuid
from pathlib import Path


def read_at(fd, relative, pub):
    names = pub.parts(relative)
    if len(names) == 1:
        return pub.regular_bytes(fd, names[0])
    with pub.directory(fd, '/'.join(names[:-1])) as parent:
        return pub.regular_bytes(parent, names[-1])


def tree(fd, prefix, pub):
    output = {}
    with pub.directory(fd, prefix) as folder:
        for name in sorted(os.listdir(folder)):
            path = prefix + '/' + name
            mode = os.stat(name, dir_fd=folder, follow_symlinks=False).st_mode
            if stat.S_ISDIR(mode):
                output.update(tree(fd, path, pub))
            elif stat.S_ISREG(mode):
                output[path] = pub.regular_bytes(folder, name)
            else:
                raise pub.PreparationError('linked/nonregular candidate input: ' + path)
    return output


def payload(run_fd, pub):
    result = {name: read_at(run_fd, name, pub) for name in ('run.json', 'result.json', 'preview-result.json')}
    result['preview-audit.json'] = read_at(run_fd, 'work/preview-audit.json', pub)
    source = json.loads(result['run.json'])
    ready = json.loads(result['preview-result.json'])
    audit = json.loads(result['preview-audit.json'])
    if json.loads(result['result.json'])['status'] != 'PREPARED' or ready['status'] != 'PREVIEW_READY':
        raise pub.PreparationError('candidate requires committed preparation and preview success')
    if ready['audit_sha256'] != pub.digest(result['preview-audit.json']) or ready['execution_id'] != audit['execution_id']:
        raise pub.PreparationError('candidate audit binding mismatch')
    if audit['source_build_id'] != source['build_id'] or audit['status'] != 'BUILT_FOR_REVIEW':
        raise pub.PreparationError('candidate source identity mismatch')
    if source['build_id'] != pub.digest(pub.canonical(source['identity'])):
        raise pub.PreparationError('candidate preparation identity mismatch')
    if audit['execution_id'] != pub.digest(json.dumps(audit['execution_identity'], sort_keys=True, separators=(',', ':')).encode()):
        raise pub.PreparationError('candidate execution identity mismatch')
    for view in audit['views']:
        required = ('missing_text_blocks', 'missing_table_row_relations', 'section_errors', 'inline_literal_errors', 'orphan_headings', 'navigation_errors')
        if any(view.get(key) != [] for key in required) or view['pages'] != view['rendered_pages'] or any(v > 2 for v in view['overfull_hbox_pt']):
            raise pub.PreparationError('candidate has missing or failed preview checks')
    artifacts = {a['pdf']: a['sha256'] for a in audit['views']}
    if artifacts != ready['artifacts'] or not artifacts:
        raise pub.PreparationError('candidate PDF set mismatch')
    for name, data in tree(run_fd, 'work/output', pub).items():
        result[name.removeprefix('work/')] = data
    if {n for n in result if n.startswith('output/pdf/')} != set(artifacts):
        raise pub.PreparationError('candidate PDF file collection mismatch')
    for name, digest in artifacts.items():
        if pub.digest(result[name]) != digest:
            raise pub.PreparationError('candidate PDF digest changed: ' + name)
    frozen = tree(run_fd, 'inputs', pub)
    expected = {i['path']: i for i in source['identity']['inputs']}
    if {n.removeprefix('inputs/') for n in frozen} != set(expected):
        raise pub.PreparationError('candidate frozen input collection mismatch')
    for name, data in frozen.items():
        identity = expected[name.removeprefix('inputs/')]
        if pub.digest(data) != identity['sha256'] or len(data) != identity['bytes']:
            raise pub.PreparationError('candidate frozen input digest mismatch: ' + name)
    result.update(frozen)
    source_bindings = {s['path']: s for s in source['identity']['publication']['sources']}
    expected_sources = {'output/source/' + path for path in source_bindings}
    if {n for n in result if n.startswith('output/source/')} != expected_sources or 'output/README.md' not in result:
        raise pub.PreparationError('candidate source attachment collection mismatch')
    for name, data in result.items():
        if name.startswith('output/source/') and data != frozen.get('inputs/' + source_bindings[name.removeprefix('output/source/')]['snapshot_path']):
            raise pub.PreparationError('candidate source attachment differs from frozen source')
    result['evidence/source-catalog.json'] = read_at(run_fd, 'work/source-catalog.json', pub)
    result['evidence/worker.log'] = read_at(run_fd, 'work/worker.log', pub)
    for prefix in ('work/source-ast', 'work/typeset'):
        for name, data in tree(run_fd, prefix, pub).items():
            if not name.endswith(('.pdf', '.png')):
                result['evidence/' + name.removeprefix('work/')] = data
    if 'reading-review.json' in os.listdir(run_fd):
        review = read_at(run_fd, 'reading-review.json', pub)
        record = json.loads(review)
        if record['artifacts'] != artifacts or record['audit_sha256'] != ready['audit_sha256']:
            raise pub.PreparationError('reading review belongs to different bytes')
        result['reading-review.json'] = review
    return result, source, ready


def freeze(root, relative, pub, profile):
    if not re.fullmatch(r'publication/build/preview/[0-9a-f]{64}/[0-9a-f]{32}', relative):
        raise pub.PreparationError('--from-preview must be a repository-relative publication/build/preview/<id>/<attempt>')
    with pub.root_handle(root) as root_fd, pub.directory(root_fd, relative) as run_fd:
        files, source, ready = payload(run_fd, pub)
        if source['identity']['publication']['profile'] != profile:
            raise pub.PreparationError('candidate profile does not match preview')
        if relative.split('/')[-2:] != [source['build_id'], source['attempt_id']]:
            raise pub.PreparationError('preview path identity mismatch')
        # Freeze precisely the captured bytes. No compiler or source worktree is read.
        identity = {'schema_version': 1, 'purpose': 'DRAFT_READING_CANDIDATE_FOR_REVIEW',
                    'preparation_id': source['build_id'], 'preview_attempt': source['attempt_id'],
                    'execution_id': ready['execution_id'], 'source_context': source['identity']['source'],
                    'publication': source['identity']['publication'],
                    'files': [{'path': n, 'bytes': len(d), 'sha256': pub.digest(d)} for n, d in sorted(files.items())]}
        candidate_id = pub.digest(pub.canonical(identity))
        attempt = uuid.uuid4().hex
        target = f'publication/build/candidate/{candidate_id}/{attempt}'
        with pub.directory(root_fd, f'publication/build/candidate/{candidate_id}', create=True) as candidates:
            os.mkdir(attempt, mode=0o700, dir_fd=candidates)
            with pub.directory(candidates, attempt) as candidate_fd:
                terminal = pub.ResultCommit(candidate_fd, 'candidate-result.json')
                outcome = {'status': 'CANDIDATE_PREPARED_FOR_REVIEW', 'candidate_id': candidate_id, 'path': str(root / target)}
                try:
                    for name, data in files.items():
                        pub.write_bytes(candidate_fd, name, data)
                    manifest = {'identity': identity, 'candidate_id': candidate_id,
                                'status': 'AWAITING_INDEPENDENT_REVIEW', 'formal_release': False, 'content_baseline_approval': False,
                                'reading_review': 'ATTACHED_SELF_REVIEW_NOT_APPROVAL' if 'reading-review.json' in files else 'NOT_ATTACHED',
                                'created_at': pub.now(), 'candidate_freezer_sha256': pub.digest(Path(__file__).read_bytes()),
                                'meaning': 'Exact existing preview bytes; no recompilation. Not a publication approval; tools/fonts are bound by identity, not bundled.'}
                    pub.write_json(candidate_fd, 'candidate-manifest.json', manifest)
                    for name, data in files.items():
                        if read_at(candidate_fd, name, pub) != data:
                            raise pub.PreparationError('candidate copied bytes changed')
                    if payload(run_fd, pub)[0] != files:
                        raise pub.PreparationError('preview changed during candidate freeze')
                    terminal.commit({**outcome, 'manifest_sha256': pub.digest(read_at(candidate_fd, 'candidate-manifest.json', pub)),
                                     'commit_protocol': pub.POLICY['result_commit_policy'], 'formal_release': False})
                    return outcome
                except BaseException as error:
                    if terminal.is_committed():
                        return outcome
                    try:
                        pub.ResultCommit(candidate_fd, 'candidate-result.json').commit({'status': 'CANCELLED' if isinstance(error, (pub.Cancelled, KeyboardInterrupt)) else 'FAILED', 'diagnostic': str(error)})
                    except (OSError, pub.Cancelled, KeyboardInterrupt):
                        pass
                    raise
