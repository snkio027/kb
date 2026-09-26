"""Frozen handbook prose metadata and a strictly enumerated HTML semantic layer."""
import json
import re


def adapt(ast, source, text):
    if ast['meta']:
        raise RuntimeError('handbook expects prose metadata, not another product front matter')
    blocks = ast['blocks']
    for i, block in enumerate(blocks):
        if block['t'] == 'Para' and block['c'] and all(n['t'] == 'RawInline' and n['c'][0] == 'html' for n in block['c']):
            blocks[i] = {'t': 'RawBlock', 'c': ['html', ''.join(n['c'][1] for n in block['c'])]}
    title = text(blocks[0]) if blocks and blocks[0]['t'] == 'Header' and blocks[0]['c'][0] == 1 else ''
    version_line = next((text(b) for b in blocks if text(b).startswith('版本：')), '')
    if not title.startswith(source['id'] + ' · ') or not re.match(r'版本：\s*' + re.escape(source['version']) + r'\s*·', version_line):
        raise RuntimeError('handbook source ID/title/version drift')
    meta = {'title': title, 'document_id': source['id'], 'version': source['version'],
            'status': 'ACCEPTED CONTENT / PILOT PDF', 'subtitle': 'Professional Handbook · 阅读试件', 'owner': ''}
    aliases, semantic, output = {}, [], []
    current = None
    for i, block in enumerate(blocks):
        if block['t'] == 'Header':
            current = block['c'][1][0]
        if block['t'] != 'RawBlock':
            output.append(block)
            continue
        format_, value = block['c']
        found = re.fullmatch(r'<a id="([A-Za-z][A-Za-z0-9-]*)"></a>\s*', value)
        if format_ == 'html' and found:
            target = current
            # An anchor immediately before a heading belongs to that heading;
            # several consecutive aliases may point to the same next heading.
            for following in blocks[i + 1:]:
                if following['t'] == 'RawBlock':
                    continue
                if following['t'] == 'Header':
                    target = following['c'][1][0]
                break
            key = found[1]
            if not target or key in aliases:
                raise RuntimeError('unbound or repeated explicit source anchor: ' + key)
            aliases[key] = target
            semantic.append({'kind': 'anchor', 'source_id': key, 'heading': target,
                             'disposition': 'PDF_DESTINATION_ALIAS'})
        elif format_ == 'html' and re.fullmatch(r'<!-- h-(lab|file) .*? -->\s*', value, re.S):
            kind, payload = re.fullmatch(r'<!-- h-(lab|file) (.*?) -->\s*', value, re.S).groups()
            payload = json.loads(payload)
            semantic.append({'kind': kind, 'payload': payload,
                             'disposition': 'NON_RENDERING_EXPERIMENT_METADATA; visible source identity retained'})
        else:
            raise RuntimeError('unrecognized handbook raw markup; not silently removed: ' + value[:120])
    ast['blocks'] = output
    return meta, aliases, semantic
