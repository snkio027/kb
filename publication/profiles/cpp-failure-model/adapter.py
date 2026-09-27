"""Frozen GFM source -> printing AST, without changing prose or code payloads.

Explicit anchors stay at the following source block, including old sections
now represented by bold paragraphs. They are never rounded to an ancestor.
"""
import json
import re


def walk(value):
    if isinstance(value, dict):
        yield value
        yield from walk(value.get('c'))
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def adapt(ast, source, text):
    blocks, pending, semantic = [], [], []
    marker = None
    section = ''
    code_number = 0
    for block in ast['blocks']:
        raw = None
        if block['t'] == 'RawBlock' and block['c'][0] == 'html':
            raw = block['c'][1]
        elif block['t'] == 'Para' and all(n['t'] in ('RawInline','Space','SoftBreak') for n in block['c']):
            raw = ''.join(n['c'][1] if n['t']=='RawInline' and n['c'][0]=='html' else '\n' for n in block['c'])
        if raw is not None:
            if re.fullmatch(r'(?:<a id="[^"<>]+"></a>\s*)+', raw):
                pending.extend(re.findall(r'<a id="([^"]+)"></a>', raw))
                continue
            match = re.fullmatch(r'<!-- fm-test (.*?) -->\s*', raw, re.S)
            if match and marker is None:
                marker = json.loads(match[1])
                continue
            raise RuntimeError('unrecognized source markup: ' + raw)
        if pending:
            if block['t'] not in ('Header','Para','Plain'):
                raise RuntimeError('anchor before unsupported block: ' + block['t'])
            inlines = block['c'][2] if block['t']=='Header' else block['c']
            for identifier in reversed(pending):
                inlines.insert(0, {'t':'Span','c':[[identifier,['source-target'],[]],[]]})
            semantic.extend({'kind':'source-target','id':a,'target_type':block['t'],
                             'target_text':text(block)} for a in pending)
            pending = []
        if block['t'] == 'Header':
            section = text(block)
        if block['t'] == 'CodeBlock':
            code_number += 1
            attrs = block['c'][0][2]
            caption = source['id'] + ' · ' + section
            if marker:
                attrs.extend([['reading-kind','experiment'], ['reading-caption',marker['id'] + ' · sample.cpp']])
                semantic.append({'kind':'test','payload':marker,'code':code_number,
                                 'filename':'sample.cpp','filename_origin':'publication-generated, single source block'})
                marker = None
            else:
                attrs.append(['reading-caption',caption])
            if blocks and blocks[-1]['t']=='Para':
                label = text(blocks[-1])
                if label in ('错误：','错误示例：','反例：','不要：','不要写：','危险：'):
                    attrs.append(['reading-bind-label',label])
                    semantic.append({'kind':'explicit-code-role','code':code_number,'label':label})
            if source['id']=='FM-9' and 'markdown' in block['c'][0][1]:
                semantic.append({'kind':'literal-template','code':code_number,'title':section})
        elif marker:
            raise RuntimeError('experiment marker does not immediately precede code')
        blocks.append(block)
    if pending or marker:
        raise RuntimeError('unconsumed source marker')
    ast['blocks'] = blocks
    if not blocks or blocks[0]['t']!='Header' or blocks[0]['c'][0]!=1 or ast['meta']:
        raise RuntimeError('unexpected document identity')
    if any(n.get('t') in ('RawBlock','RawInline','Cite') for n in walk(blocks)):
        raise RuntimeError('unhandled source markup')
    return {'document_id':source['id'], 'title':text(blocks[0]), 'version':source['version'],
            'status':'ACCEPTED CONTENT', 'owner':'', 'subtitle':'Frozen source @ 45b305e'}, {}, semantic
