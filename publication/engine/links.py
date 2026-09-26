"""Resolve repository-relative identities, never basename substitutions."""
import json
import posixpath
import re
from urllib.parse import quote, unquote, urlsplit
from source_model import blob


class Resolver:
    def __init__(self, documents, selected, repository, origin, tools, pub, command, work, walk):
        self.documents = {d['relative_path']: d for d in documents}
        self.selected = {d['id'] for d in selected}
        self.repository, self.origin, self.tools, self.pub = repository, origin, tools, pub
        self.command, self.work, self.walk = command, work, walk
        self.cache, self.ledger = {}, []

    def resolve(self, target, doc):
        uri = urlsplit(target)
        if uri.scheme or uri.netloc or uri.path.startswith('/') or uri.query:
            self.ledger.append({'from': doc['id'], 'source': target, 'kind': 'EXTERNAL_URI', 'target': target})
            return target
        path = posixpath.normpath(posixpath.join(posixpath.dirname(doc['relative_path']), unquote(uri.path))) if uri.path else doc['relative_path']
        if path == '..' or path.startswith('../'):
            raise RuntimeError('reference escapes repository: ' + target)
        fragment = unquote(uri.fragment)
        dest = self.documents.get(path)
        if dest:
            destination = (dest['anchors'].get(fragment) or (fragment if fragment in dest['aliases'] else None)) if fragment else dest['first_anchor']
            if not destination:
                raise RuntimeError('unresolved source anchor: ' + target)
            if dest['id'] in self.selected:
                resolved, kind = '#' + destination, 'SAME_VIEW_INTERNAL'
            else:
                resolved, kind = dest['source_href'] + ('#' + quote(fragment) if fragment else ''), 'EXTERNAL_SOURCE'
        else:
            key = (doc['source']['commit'], path)
            if key not in self.cache:
                raw = blob(self.origin, key[0], path, self.pub)
                ids = set()
                if path.endswith('.md'):
                    parsed = json.loads(self.command([self.tools['pandoc'], '-f', 'markdown-smart', '-t', 'json'], self.work, input_data=raw))
                    ids.update(n['c'][1][0] for n in self.walk(parsed['blocks']) if n.get('t') == 'Header')
                    ids.update(re.findall(r'<a id="([^"]+)"></a>', raw.decode()))
                    # GitHub/GFM keeps leading heading numbers unlike Pandoc.
                    for line in raw.decode().splitlines():
                        if re.match(r'^#{1,6} ', line):
                            value = re.sub(r'[^\w\- ]', '', re.sub(r'^#+ ', '', line).lower())
                            ids.add(value.replace(' ', '-'))
                self.cache[key] = ids
            if fragment and fragment not in self.cache[key]:
                raise RuntimeError('unresolved external-source fragment: ' + target)
            resolved = self.repository + '/blob/' + key[0] + '/' + quote(path) + ('#' + quote(fragment) if fragment else '')
            kind = 'EXTERNAL_SOURCE'
        self.ledger.append({'from': doc['id'], 'source': target, 'kind': kind, 'target': resolved})
        return resolved
