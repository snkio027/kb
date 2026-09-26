"""Bounded PDF fidelity checks: source sections, consumed occurrences, order,
literal spaces and navigation targets. Not a semantic/visual approval engine.
"""
import re
from collections import Counter


def ordered_match(samples, actual, normalize):
    """Consume each occurrence once, in its own section; never reuse a hit."""
    value = normalize(actual)
    cursor, matches, failures = 0, [], []
    for index, sample in enumerate(samples):
        needle = normalize(sample)
        if not needle:
            continue
        at = value.find(needle, cursor)
        if at < 0:
            failures.append({"unit": index, "text": sample, "reason": "missing, repeated occurrence lost, or out of order"})
        else:
            matches.append({"unit": index, "start": at, "end": at + len(needle)})
            cursor = at + len(needle)
    counts = Counter(normalize(s) for s in samples if normalize(s))
    return matches, failures, [{"text": s, "expected_occurrences": n, "available_occurrences": value.count(s)} for s, n in counts.items() if n > 1]


def literal_pattern(literal):
    # Line endings may represent a permitted layout break, never deleted spaces
    # inside a same-line literal. Ordinary prose normalization is NOT used here.
    out, run = [], 0
    for token in re.findall(r" +|[^ ]", literal):
        if token.startswith(" "):
            out.append(r"(?:[ \t]{" + str(len(token)) + r"}[\r\n]*|[ \t]*\r?\n[ \t]*)")
            run = 0
        else:
            out.append(re.escape(token))
            run += 1
            if token in "_/.:=-" or run >= 28:
                out.append(r"[\r\n]*")
                run = 0
    return "".join(out)


def pdf_fragments(reader):
    pages = []
    for page in reader.pages:
        fragments = []
        def capture(value, cm, tm, font, size):
            y = tm[5] * cm[3] + cm[5]
            if value and 52 < y < 782:
                fragments.append({"text": value, "y": y})
        page.extract_text(visitor_text=capture)
        pages.append(fragments)
    return pages


def destination_position(reader, name):
    target = reader.named_destinations[name]
    return reader.get_destination_page_number(target), -float(target["/Top"])


def window(pages, start, end, ignored, normalize):
    raw, normalized, page_map = [], [], []
    for page in range(start[0], min(end[0] + 1, len(pages))):
        for fragment in pages[page]:
            if start <= (page, -fragment["y"]) < end:
                raw.append(fragment["text"])
                sample = normalize(fragment["text"])
                normalized.append(sample)
                page_map.extend([page + 1] * len(sample))
    value = "".join(normalized)
    for label in ignored:
        needle = normalize(label)
        while needle in value:
            at = value.index(needle)
            value = value[:at] + value[at + len(needle):]
            del page_map[at:at + len(needle)]
    return "".join(raw), value, page_map


def section_audit(reader, documents, ledger, ignored, profile, combined):
    from preview import normalize, text, walk
    pages = pdf_fragments(reader)
    navigation = profile["navigation"]
    index_policy = profile.get("index") if combined else None
    sections = []
    for doc in documents:
        table_number = 0
        for block in doc["ast"]["blocks"]:
            if block["t"] == "Header":
                sections.append({"document": doc["id"], "anchor": doc["anchors"][block["c"][1][0]], "title": text(block),
                                 "units": [text(block)], "literals": [text(c) for c in walk(block) if c["t"] == "Code"]})
                continue
            if not sections or sections[-1]["document"] != doc["id"]:
                raise RuntimeError("source block before first document heading requires explicit handling")
            section = sections[-1]
            if block["t"] == "Table":
                table_number += 1
                table = next(t for t in ledger if t["table"] == f'{doc["id"]}-T{table_number:02}')
                if table["layout"] == "matrix" or not table["row_text"]:
                    section["units"].append("".join(table["headers"]))
                section["units"].extend(table["row_text"])
            else:
                section["units"].extend(text(n) for n in walk(block) if n["t"] in ("Para", "Plain", "CodeBlock"))
            section["literals"].extend(text(n) for n in walk(block) if n["t"] == "Code")

    results, errors, literal_errors, orphans = [], [], [], []
    positions = [destination_position(reader, s["anchor"]) for s in sections]
    if positions != sorted(positions) or len(positions) != len(set(positions)):
        raise RuntimeError("source headings reversed or share the same PDF position")
    finish = destination_position(reader, index_policy["id"]) if index_policy else (len(pages), 0)
    for index, section in enumerate(sections):
        start = positions[index]
        end = positions[index + 1] if index + 1 < len(positions) else finish
        raw, actual, page_map = window(pages, start, end, ignored, normalize)
        matches, missing, counts = ordered_match(section["units"], actual, normalize)
        if not actual.startswith(normalize(section["title"])):
            errors.append({"anchor": section["anchor"], "reason": "destination region does not start with expected source title"})
        errors.extend({"anchor": section["anchor"], **m} for m in missing)
        # A separate, whitespace-sensitive literal check. Consume in source order.
        literal_cursor = 0
        literal_text = raw
        for literal in section["literals"]:
            found = re.search(literal_pattern(literal), literal_text[literal_cursor:])
            if found is None:
                literal_errors.append({"anchor": section["anchor"], "literal": literal})
            else:
                literal_cursor += found.end()
        title_hit = next((m for m in matches if m["unit"] == 0), None)
        first_body = next((m for m in matches if m["unit"] > 0), None)
        results.append({"document": section["document"], "anchor": section["anchor"], "title": section["title"],
                        "start_page": start[0] + 1, "end_page": end[0] + 1, "expected_units": len(section["units"]),
                        "matched_units": len(matches), "duplicate_samples": counts, "inline_literals_checked": len(section["literals"]),
                        "title_end_page": page_map[title_hit["end"] - 1] if title_hit else None,
                        "first_body_page": page_map[first_body["start"]] if first_body else None})
    for index, item in enumerate(results):
        meaningful = next((s for s in results[index:] if s["first_body_page"] is not None), None)
        if meaningful and item["title_end_page"] != meaningful["first_body_page"]:
            orphans.append({"anchor": item["anchor"], "title": item["title"], "title_page": item["title_end_page"], "first_body_page": meaningful["first_body_page"]})
    # Generated preface is validated against actual content, not name existence.
    preface = destination_position(reader, navigation["preface_id"])
    _, preface_text, _ = window(pages, preface, (preface[0] + 1, -10000), (), normalize)
    if not preface_text.startswith(normalize(navigation["preface_title"])):
        errors.append({"anchor": navigation["preface_id"], "reason": "wrong target region"})
    navigation_errors = []
    outline_targets = {}
    def outline_walk(entries, parents=()):
        previous = None
        for entry in entries:
            if isinstance(entry, list):
                if previous is not None:
                    outline_walk(entry, parents + (previous,))
            else:
                position = (reader.get_destination_page_number(entry), -float(entry.get('/Top', 0)))
                outline_targets[position] = (parents, entry)
                previous = position
    outline_walk(reader.outline)
    for doc in documents:
        first = destination_position(reader, doc['anchors'][next(iter(doc['anchors']))])
        for identifier in doc['anchors'].values():
            position = destination_position(reader, identifier)
            found = outline_targets.get(position)
            if found is None or (position != first and (not found[0] or found[0][0] != first)):
                navigation_errors.append({'anchor': identifier, 'reason': 'bookmark absent or outside owning document group'})
    found = outline_targets.get(preface)
    if not found or normalize(str(found[1]['/Title'])) != normalize(navigation['preface_title']):
        navigation_errors.append({'anchor': navigation['preface_id'], 'reason': 'preface bookmark points to wrong region'})
    # Verify the actual title link in the front TOC, not merely a same-named target.
    preface_links = 0
    for number in range(preface[0] + 1, positions[0][0]):
        for ref in reader.pages[number].get('/Annots', []):
            annotation = ref.get_object()
            rect = annotation.get('/Rect', [])
            if len(rect) != 4:
                continue
            line = ''.join(f['text'] for f in pages[number] if float(rect[1]) - 2 <= f['y'] <= float(rect[3]) + 2)
            if normalize(navigation['preface_title']) in normalize(line):
                target = annotation.get('/Dest') or annotation.get('/A', {}).get('/D')
                if target == navigation['preface_id']:
                    preface_links += 1
                else:
                    navigation_errors.append({'anchor': navigation['preface_id'], 'reason': 'front TOC link does not use the explicit preface target'})
    if not preface_links:
        navigation_errors.append({'anchor': navigation['preface_id'], 'reason': 'front TOC preface link not verified'})
    index_entries = 0
    if index_policy:
        _, index_text, _ = window(pages, finish, (len(pages), 0), (), normalize)
        for doc in documents:
            for header in (n for n in walk(doc['ast']['blocks']) if n['t'] == 'Header' and re.search(index_policy['heading_pattern'], text(n))):
                target = doc['anchors'][header['c'][1][0]]
                page = destination_position(reader, target)[0] + 1
                if normalize(text(header)) + str(page) not in index_text:
                    navigation_errors.append({'anchor': target, 'reason': 'printed generated index page does not match PDF destination'})
                index_entries += 1
    return {"sections": results, "section_errors": errors, "inline_literal_errors": literal_errors, "orphan_headings": orphans,
            "navigation_errors": navigation_errors, "index_entries_checked": index_entries,
            "top_level_bookmarks": len([n for n in reader.outline if isinstance(n, dict)]),
            "preface_page": preface[0] + 1, "policy": "Ordered, non-reused source occurrences within exact heading regions; literal whitespace checked separately; no claim of complete code-block indentation or visual certification"}
