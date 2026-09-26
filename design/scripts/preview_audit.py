"""Compatibility import for read-only audit helpers."""
from pathlib import Path
import importlib.util
_path = Path(__file__).resolve().parents[2] / "publication/engine/preview_audit.py"
_spec = importlib.util.spec_from_file_location("kb_preview_audit", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
for _name in ("ordered_match", "literal_pattern", "pdf_fragments", "destination_position", "window", "section_audit"):
    globals()[_name] = getattr(_module, _name)
