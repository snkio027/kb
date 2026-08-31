#!/usr/bin/env bash
set -euo pipefail

design_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$design_dir"

dpi="${PDF_RENDER_DPI:-180}"
python_cmd="${PYTHON_BIN:-python3}"

mkdir -p \
  tmp/pdfs/render-method-poppler \
  tmp/pdfs/render-reference-poppler \
  tmp/pdfs/render-method-pdfium \
  tmp/pdfs/render-reference-pdfium
rm -f \
  tmp/pdfs/render-method-poppler/page-*.png \
  tmp/pdfs/render-reference-poppler/page-*.png \
  tmp/pdfs/render-method-pdfium/page-*.png \
  tmp/pdfs/render-reference-pdfium/page-*.png

pdftoppm -png -r "$dpi" output/pdf/01-优秀系统设计与工程保证方法论-v1.1.0.pdf tmp/pdfs/render-method-poppler/page
pdftoppm -png -r "$dpi" output/pdf/02-优秀系统设计-从约束不变量到证据-v1.1.0.pdf tmp/pdfs/render-reference-poppler/page

"$python_cmd" scripts/render-pdfium.py \
  output/pdf/01-优秀系统设计与工程保证方法论-v1.1.0.pdf \
  tmp/pdfs/render-method-pdfium \
  "$dpi"
"$python_cmd" scripts/render-pdfium.py \
  output/pdf/02-优秀系统设计-从约束不变量到证据-v1.1.0.pdf \
  tmp/pdfs/render-reference-pdfium \
  "$dpi"
