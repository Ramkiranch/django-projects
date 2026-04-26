#!/usr/bin/env bash
# Self-host the three font families used by the design.
#
# Sources WOFF2 files from the google-webfonts-helper API
# (https://gwfh.mranftl.com) — same URLs you'd otherwise paste into
# <link>. The output lands in static/fonts/ next to tokens.css's
# @font-face declarations.
#
# Re-runnable: skips files that already exist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FONTS_DIR="${SCRIPT_DIR}/../static/fonts"
mkdir -p "${FONTS_DIR}"

GWFH="https://gwfh.mranftl.com/api/fonts"

fetch() {
  local family="$1" weight="$2" style="$3" out="$4"
  if [[ -f "${FONTS_DIR}/${out}" ]]; then
    echo "[skip] ${out}"
    return
  fi
  local url
  url="${GWFH}/${family}?download=zip&subsets=latin&variants=${weight}${style:+${style}}&formats=woff2"
  local tmp
  tmp="$(mktemp -d)"
  echo "[fetch] ${family} ${weight}${style} → ${out}"
  curl -fsSL "${url}" -o "${tmp}/font.zip"
  unzip -q -o "${tmp}/font.zip" -d "${tmp}"
  # zip contains <family>-v<n>-latin-<variant>.woff2 — pick the only .woff2
  local woff2
  woff2="$(ls "${tmp}"/*.woff2 | head -n 1)"
  cp "${woff2}" "${FONTS_DIR}/${out}"
  rm -rf "${tmp}"
}

fetch fraunces 300 ""       fraunces-300.woff2
fetch fraunces 300 "italic" fraunces-300-italic.woff2
fetch fraunces 400 ""       fraunces-400.woff2
fetch fraunces 400 "italic" fraunces-400-italic.woff2

fetch inter 400 "" inter-400.woff2
fetch inter 500 "" inter-500.woff2

fetch caveat 400 "" caveat-400.woff2
fetch caveat 600 "" caveat-600.woff2

echo "Done. Fonts written to ${FONTS_DIR}"
