#!/usr/bin/env bash
set -euo pipefail

design_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$design_dir"

export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1788134400}"
export FORCE_SOURCE_DATE=1

mkdir -p build dist tmp/pdfs/texmf-var tmp/pdfs/texmf-cache

filters=(
  publication/filters/pdf-metadata.lua
  publication/filters/normalize-headings.lua
  publication/filters/semantic-blocks.lua
  publication/filters/tables.lua
  publication/filters/code-blocks.lua
  publication/filters/cross-references.lua
)

build_one() {
  local source="$1"
  local stem="${source%.md}"
  local tex="build/${stem}.tex"
  local pdf="build/${stem}.pdf"

  local args=("$source" --from=markdown+yaml_metadata_block+smart --to=latex --standalone
    --top-level-division=chapter --wrap=none --template=publication/template.tex
    --metadata-file=publication/profiles/release.yaml --output="$tex")
  for filter in "${filters[@]}"; do args+=(--lua-filter="$filter"); done
  pandoc "${args[@]}"

  openout_any=a TEXMFVAR="$design_dir/tmp/pdfs/texmf-var" TEXMFCACHE="$design_dir/tmp/pdfs/texmf-cache" \
    TEXINPUTS="$design_dir/publication//:" \
    latexmk -lualatex -interaction=nonstopmode -halt-on-error -file-line-error \
    -outdir=build "$tex"

  cp "$pdf" "dist/${stem}.pdf"
}

build_one "01-优秀系统设计与工程保证方法论-v1.1.0.md"
build_one "02-优秀系统设计-从约束不变量到证据-v1.1.0.md"

sha256sum dist/*.pdf > dist/sha256sums.txt
python3 scripts/write-manifest.py
