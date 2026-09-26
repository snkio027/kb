"""ESD front matter is the product authority; no handbook assumptions."""
def adapt(ast, source, text):
    meta = {key: text(value) for key, value in ast["meta"].items()}
    if meta.get("document_id") != source["id"] or "DRAFT" not in meta.get("status", ""):
        raise RuntimeError("ESD requires matching document_id and DRAFT front matter")
    for key in ("title", "version", "status"):
        if not meta.get(key):
            raise RuntimeError("ESD missing metadata: " + key)
    return meta, {}, []
