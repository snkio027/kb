"""RC1 changes generated publication metadata only; accepted source AST unchanged."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / 'cpp-handbook-full' / 'adapter.py'
_spec = importlib.util.spec_from_file_location('accepted_fullbook_adapter', _path)
_full = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_full)


def adapt(ast, source, text):
    meta, aliases, semantic = _full.adapt(ast, source, text)
    meta.update(status='ACCEPTED CONTENT', subtitle='Professional Handbook')
    return meta, aliases, semantic
