"""Full-book source integration; reuse the frozen Pilot adapter, not its layout.

The four accepted experiment registries use g/h/n/s comment namespaces. Only
those explicit non-printing markers are normalized in the parsing copy; their
original namespace and complete payload remain in the semantic ledger.
"""
import importlib.util
import json
import re
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / 'cpp-handbook' / 'adapter.py'
_spec = importlib.util.spec_from_file_location('frozen_pilot_adapter', _path)
_pilot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pilot)

_LITERALS = {
    'G3': {'<int>': 2, '<T>': 4},
    'G4': {'<bool>': 1, '<pair>': 1, '<T>': 2, '<const T>': 1},
    'G5': {'<T>': 1, '<Endian::Little>': 1, '<Endian::Big>': 1, '<int>': 1},
}


def walk(value):
    if isinstance(value, dict):
        yield value
        yield from walk(value.get('c'))
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def adapt(ast, source, text):
    # Consecutive explicit anchors in later chapters form a Para with HTML
    # RawInline plus SoftBreak nodes. Split only anchor-only paragraphs; leave
    # mixed prose/unknown HTML to the existing strict rejection path.
    blocks = []
    for block in ast['blocks']:
        if block['t'] == 'Para' and block['c'] and all(
            n['t'] in ('Space', 'SoftBreak') or
            (n['t'] == 'RawInline' and n['c'][0] == 'html') for n in block['c']):
            value = ''.join(n['c'][1] if n['t']=='RawInline' else '\n' for n in block['c'])
            anchor = r'<a id="[A-Za-z][A-Za-z0-9-]*"></a>'
            if re.fullmatch('(?:'+anchor+r'\s*)+', value):
                blocks.extend({'t':'RawBlock', 'c':['html',a]} for a in re.findall(anchor, value))
                continue
        blocks.append(block)
    ast['blocks'] = blocks
    namespaces = []
    lab_namespace = None
    pending = False
    for block in ast['blocks']:
        if block['t'] == 'CodeBlock':
            pending = False
        if block['t'] != 'RawBlock' or block['c'][0] != 'html':
            continue
        match = re.fullmatch(r'<!-- ([ghns])-(lab|file) (.*?) -->\s*', block['c'][1], re.S)
        if not match:
            continue  # The original adapter rejects any unsupported raw markup.
        namespace, kind, raw_payload = match.groups()
        payload = json.loads(raw_payload)
        if kind == 'lab':
            if pending or not payload['id'].startswith(source['id'] + '-'):
                raise RuntimeError('unconsumed file or wrong experiment owner')
            lab_namespace = namespace
        else:
            if pending or namespace != lab_namespace or not payload.get('path'):
                raise RuntimeError('file without matching experiment namespace')
            pending = True
        namespaces.append(namespace)
        block['c'][1] = '<!-- h-' + kind + ' ' + raw_payload + ' -->\n'
    if pending:
        raise RuntimeError('unconsumed experiment file identity')
    meta, aliases, semantic = _pilot.adapt(ast, source, text)
    markers = [entry for entry in semantic if entry['kind'] in ('lab', 'file')]
    if len(markers) != len(namespaces):
        raise RuntimeError('experiment registry mapping lost')
    for marker, namespace in zip(markers, namespaces):
        marker['source_namespace'] = namespace
    # Pandoc mistakes Mach-O @rpath/@loader_path prose for bibliography cites.
    # These exact two source tokens are literal loader syntax, not citations.
    citations = {}
    for node in walk(ast['blocks']):
        if node.get('t') != 'Cite':continue
        value = text(node)
        if source['id'] not in ('G8','G9') or value not in ('@rpath','@loader_path'):
            raise RuntimeError('unexpected source citation requires explicit review')
        citations[value] = citations.get(value,0)+1
        node.update(t='Span',c=[['',[],[]],node['c'][1]])
        semantic.append({'kind':'loader-literal','value':value,'disposition':'EXACT_PRINTED_SOURCE_CHARACTERS; not bibliography'})
    expected_citations = {'@rpath':1,'@loader_path':1} if source['id'] in ('G8','G9') else {}
    if citations != expected_citations:raise RuntimeError('loader literal inventory drift')
    # These frozen prose spellings are C++ template arguments, not HTML. Print
    # their exact characters and bind their occurrence counts. Unknown HTML
    # still fails; never strip arbitrary tags or repair the authoritative file.
    observed = {}
    for node in walk(ast['blocks']):
        if node.get('t') == 'RawInline' and node['c'][0] == 'html':
            value = node['c'][1]
            if value not in _LITERALS.get(source['id'], {}):
                raise RuntimeError('unrecognized inline markup: ' + value)
            observed[value] = observed.get(value, 0) + 1
            node.update(t='Str', c=value)
            semantic.append({'kind':'literal', 'value':value, 'disposition':'EXACT_PRINTED_SOURCE_CHARACTERS'})
    if observed != _LITERALS.get(source['id'], {}):
        raise RuntimeError('frozen inline literal inventory drift')
    # The full-book G9 preset paragraph has two contrasted clauses. Start its
    # personal-preset clause as a second publishing paragraph at the existing
    # semicolon; no words, punctuation, order or authoritative bytes change.
    if source['id']=='G9':
        split=[];matched=0
        for block in ast['blocks']:
            if block['t']=='Para' and text(block).startswith('CMakePresets.json '):
                for index,node in enumerate(block['c']):
                    if node=={'t':'Str','c':'等流程；CMakeUserPresets.json'}:
                        split.extend([{'t':'Para','c':block['c'][:index]+[{'t':'Str','c':'等流程；'}]},
                                      {'t':'Para','c':[{'t':'Str','c':'CMakeUserPresets.json'}]+block['c'][index+1:]}])
                        matched+=1;break
                else:raise RuntimeError('preset paragraph boundary drift')
            else:split.append(block)
        if matched!=1:raise RuntimeError('preset paragraph count drift')
        ast['blocks']=split
        semantic.append({'kind':'paragraph-boundary','source':'G9 / 5.1 / presets',
                         'disposition':'SPLIT_AT_EXISTING_SEMICOLON; all source characters retained'})
    # Plain prose identifiers overflowed and C linkage quotes became curly.
    # Reuse the frozen inline-literal component (including delimiter breaks),
    # preserving exact text; do not change line widths or typography policy.
    literals = {'G8': {'requested_version', '"C"'}, 'G9': {'CMakeUserPresets.json'}}
    for node in walk(ast['blocks']):
        if node.get('t') != 'Str':
            continue
        value = node['c']
        for literal in literals.get(source['id'], set()):
            match = re.search(r'(?<![A-Za-z0-9_])'+re.escape(literal)+r'(?![A-Za-z0-9_])', value)
            if not match:
                continue
            parts = []
            if match.start():
                parts.append({'t':'Str','c':value[:match.start()]})
                # A CJK punctuation/token join has no Markdown word boundary.
                # Make the new inline literal a separate typographic word so
                # the existing component can move whole to the next line.
                if not value[match.start()-1].isascii():parts.append({'t':'Space'})
            parts.append({'t':'Code','c':[['',[],[]],literal]})
            if match.end()<len(value):parts.append({'t':'Str','c':value[match.end():]})
            node.update(t='Span',c=[['',['fullbook-inline-literal'],[]],parts])
            semantic.append({'kind':'inline-identifier', 'value':literal,
                             'disposition':'FROZEN_INLINE_LITERAL_COMPONENT; exact source text'})
            break
    # Splice the generated inline sequence into its owning paragraph rather
    # than create a TeX group around CJK prose + a differently spaced literal.
    # The latter can suppress legal breaks at the font/spacing boundary.
    def splice(value):
        if isinstance(value,dict):
            if 'c' in value:value['c']=splice(value['c'])
        elif isinstance(value,list):
            result=[]
            for child in value:
                child=splice(child)
                if isinstance(child,dict) and child.get('t')=='Span' and child['c'][0][1]==['fullbook-inline-literal']:
                    result.extend(child['c'][1])
                else:result.append(child)
            return result
        return value
    ast['blocks']=splice(ast['blocks'])
    meta.update(status='ACCEPTED CONTENT / FULL HANDBOOK PREVIEW',
                subtitle='Professional Handbook · 全书阅读候选')
    return meta, aliases, semantic
