#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "usage: $0 OLD.pdf NEW.pdf" >&2
  exit 2
fi

old_pdf="$1"
new_pdf="$2"
comparison_dir="$(mktemp -d)"
trap 'rm -rf "$comparison_dir"' EXIT

mkdir -p "$comparison_dir/old" "$comparison_dir/new"
pdftoppm -png -r 180 "$old_pdf" "$comparison_dir/old/page"
pdftoppm -png -r 180 "$new_pdf" "$comparison_dir/new/page"

shopt -s nullglob
old_pages=("$comparison_dir"/old/page-*.png)
new_pages=("$comparison_dir"/new/page-*.png)

if [[ "${#old_pages[@]}" -ne "${#new_pages[@]}" ]]; then
  echo "page-count changed: ${#old_pages[@]} -> ${#new_pages[@]}" >&2
  exit 1
fi

changed=0
for index in "${!old_pages[@]}"; do
  if ! cmp -s "${old_pages[$index]}" "${new_pages[$index]}"; then
    printf 'changed page: %d\n' "$((index + 1))"
    changed=1
  fi
done

exit "$changed"
