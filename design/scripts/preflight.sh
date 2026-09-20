#!/usr/bin/env bash
set -euo pipefail

design_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$design_dir"
python_cmd="${PYTHON_BIN:-python3}"
mkdir -p tmp/pdfs

resolve_pdf_tool() {
  local tool_name="$1"
  local tool_cmd
  local pdfinfo_cmd
  local bundled_candidate

  tool_cmd="$(command -v "$tool_name" || true)"
  if [[ -n "$tool_cmd" ]]; then
    printf '%s\n' "$tool_cmd"
    return 0
  fi

  pdfinfo_cmd="$(command -v pdfinfo || true)"
  if [[ -n "$pdfinfo_cmd" ]]; then
    bundled_candidate="$(dirname "$pdfinfo_cmd")/../../native/poppler/poppler/bin/$tool_name"
    if [[ -x "$bundled_candidate" ]]; then
      printf '%s\n' "$bundled_candidate"
      return 0
    fi
  fi

  return 1
}

pdffonts_cmd="$(resolve_pdf_tool pdffonts || true)"
pdftotext_cmd="$(resolve_pdf_tool pdftotext || true)"

if [[ -z "$pdffonts_cmd" ]]; then
  echo "ERROR: pdffonts is required for font-embedding checks" >&2
  exit 1
fi
if [[ -z "$pdftotext_cmd" ]]; then
  echo "ERROR: pdftotext is required for text checks" >&2
  exit 1
fi

fail=0
for pdf in dist/*.pdf; do
  echo "== $pdf =="
  pdfinfo "$pdf" | rg '^(Title|Author|Pages|Page size|PDF version|Tagged):'
  "$pdffonts_cmd" "$pdf" | sed -n '1,12p'
  if "$pdffonts_cmd" "$pdf" | tail -n +3 | awk 'NF && $(NF-4) != "yes" {exit 1}'; then :; else
    echo "ERROR: unembedded font in $pdf" >&2
    fail=1
  fi
done

for log in build/*.log; do
  if rg -n 'Undefined control sequence|LaTeX Error|Missing character|destination with the same identifier' "$log"; then
    echo "ERROR: blocking diagnostics in $log" >&2
    fail=1
  fi
  if perl -ne 'if (/Overfull \\hbox \(([0-9.]+)pt/ && $1 > 1) { print; $bad=1 } END { exit($bad ? 0 : 1) }' "$log"; then
    echo "ERROR: overfull box greater than 1 pt in $log" >&2
    fail=1
  fi
done

for stem in 01-优秀系统设计与工程保证方法论-v1.1.0 02-优秀系统设计-从约束不变量到证据-v1.1.0; do
  "$pdftotext_cmd" -layout "dist/${stem}.pdf" "tmp/pdfs/${stem}.txt"
done

rg -q '最终判定标准' tmp/pdfs/01-优秀系统设计与工程保证方法论-v1.1.0.txt || fail=1
rg -q '最小 19 问设计清单' tmp/pdfs/02-优秀系统设计-从约束不变量到证据-v1.1.0.txt || fail=1
rg -q '两篇文档的最终边界' tmp/pdfs/02-优秀系统设计-从约束不变量到证据-v1.1.0.txt || fail=1

"$python_cmd" scripts/pdf-structure-audit.py dist/*.pdf || fail=1
"$python_cmd" scripts/content-audit.py || fail=1

exit "$fail"
