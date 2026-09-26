"""Repository-relative, no-follow inputs; explicit immutable Git source revisions."""
import json
import os
import re
import subprocess
import stat
from pathlib import Path


def git(root, *args):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('GIT_', 'XCRUN_')) and k not in ('TMPDIR', 'TMP', 'TEMP')}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    return subprocess.check_output(['git', '--no-pager', '-c', 'core.fsmonitor=false',
                                    '-C', str(root), *args], env=env, stderr=subprocess.PIPE)


def path_parts(path, pub):
    if not isinstance(path, str) or not path or path != '/'.join(pub.parts(path)):
        raise pub.PreparationError('noncanonical input path')
    return pub.parts(path)


def read(root_fd, path, pub):
    names = path_parts(path, pub)
    if len(names) == 1:
        return pub.regular_bytes(root_fd, names[0])
    with pub.directory(root_fd, '/'.join(names[:-1])) as parent:
        return pub.regular_bytes(parent, names[-1])


def blob(root, revision, path, pub):
    path_parts(path, pub)
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise pub.PreparationError('source revision must be a full immutable commit SHA')
    if git(root, 'cat-file', '-t', revision).strip() != b'commit':
        raise pub.PreparationError('source revision is not a commit')
    entry = git(root, 'ls-tree', '-z', revision, '--', path).split(b'\0')
    if len(entry) != 2 or not entry[0].startswith((b'100644 blob ', b'100755 blob ')):
        raise pub.PreparationError('source must be a regular Git blob: ' + path)
    return git(root, 'cat-file', 'blob', revision + ':' + path)


def snapshot(root_fd, profile, views, pub):
    if not re.fullmatch(r'[a-z][a-z0-9-]*', profile):
        raise pub.PreparationError('invalid profile name')
    root = Path(pub.ROOT)  # Caller sets ROOT to the repository used for preparation.
    # A directory handle's identity must match the selected repository.
    if (os.fstat(root_fd).st_dev, os.fstat(root_fd).st_ino) != (root.stat().st_dev, root.stat().st_ino):
        raise pub.PreparationError('repository root/handle mismatch')
    prefix = 'publication/profiles/' + profile
    config = json.loads(read(root_fd, prefix + '/profile.json', pub))
    if config.get('schema_version') != 2 or config.get('id') != profile:
        raise pub.PreparationError('unsupported profile identity/schema')
    if not config.get('sources') or not config.get('views'):
        raise pub.PreparationError('profile requires sources and views')
    selected = views or [v['id'] for v in config['views']]
    known_views = [v['id'] for v in config['views']]
    if len(set(known_views)) != len(known_views) or len(set(selected)) != len(selected) or not set(selected) <= set(known_views):
        raise pub.PreparationError('unknown or repeated view')
    for view in config['views']:
        if not re.fullmatch(r'[A-Z][A-Z0-9-]+', view['id']):
            raise pub.PreparationError('unsafe view identity')
        if not view['documents'] or len(set(view['documents'])) != len(view['documents']):
            raise pub.PreparationError('empty/repeated view source')
    snapshot = {}
    def collect(fd, relative):
        for name in sorted(os.listdir(fd)):
            if name == '__pycache__':
                continue
            mode = os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode
            path = relative + '/' + name
            if stat.S_ISDIR(mode):
                with pub.directory(fd, name) as child:
                    collect(child, path)
            elif stat.S_ISREG(mode):
                snapshot[path] = pub.regular_bytes(fd, name)
            else:
                raise pub.PreparationError('linked/nonregular publication input: ' + path)
    for folder in ('publication/engine', 'publication/latex', prefix):
        with pub.directory(root_fd, folder) as fd:
            collect(fd, folder)
    for name in config.get('dependencies', []):
        path_parts(name, pub)
        snapshot[name] = read(root_fd, name, pub)
    for name in (prefix + '/adapter.py', prefix + '/template.tex', prefix + '/theme.sty',
                 'publication/engine/pub.py', 'publication/engine/preview.py'):
        if name not in snapshot:
            raise pub.PreparationError('missing required publication input: ' + name)
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    sources = []
    ids, paths = set(), set()
    for definition in config['sources']:
        path = definition['path']
        path_parts(path, pub)
        if not path.endswith('.md') or path in paths or definition['id'] in ids:
            raise pub.PreparationError('invalid or duplicate source')
        if not re.fullmatch(r'[A-Z][A-Z0-9-]+', definition['id']):
            raise pub.PreparationError('unsafe document ID')
        paths.add(path)
        ids.add(definition['id'])
        revision = definition['revision']
        raw = read(root_fd, path, pub) if revision == 'WORKTREE' else blob(root, revision, path, pub)
        commit = head if revision == 'WORKTREE' else revision
        try:
            matches = raw == blob(root, commit, path, pub)
        except (subprocess.CalledProcessError, pub.PreparationError):
            matches = False
        target = 'sources/' + path
        snapshot[target] = raw
        sources.append({**definition, 'commit': commit, 'snapshot_path': target,
                        'sha256': pub.digest(raw), 'bytes': len(raw), 'matches_commit': matches})
    if any(not set(v['documents']) <= ids for v in config['views']):
        raise pub.PreparationError('view refers to unknown document')
    model = {'schema_version': 2, 'profile': profile, 'profile_path': prefix,
             'repository': config['repository'], 'sources': sources, 'views': selected}
    snapshot['source-set.json'] = pub.canonical(model) + b'\n'
    return snapshot


def verify_live_inputs(run, origin, pub):
    """Refuse changed renderer/profile or worktree input; fixed Git sources stay fixed."""
    record = json.loads((run / 'run.json').read_text())
    with pub.root_handle(origin) as fd:
        for item in record['identity']['inputs']:
            path = item['path']
            if path.startswith('publication/') or not path.startswith(('sources/', 'source-set.json')):
                if pub.digest(read(fd, path, pub)) != item['sha256']:
                    raise pub.PreparationError('publication input drift: ' + path)
        for source in record['identity']['publication']['sources']:
            if source['revision'] == 'WORKTREE' and pub.digest(read(fd, source['path'], pub)) != source['sha256']:
                raise pub.PreparationError('worktree source drift: ' + source['path'])
