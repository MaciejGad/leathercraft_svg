#!/usr/bin/env bash

set -euo pipefail

PYTHON_BIN=".venv/bin/python"
COVER_DIR=".trace-coverage"
REPORT_FILE="$COVER_DIR/summary.txt"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Expected virtualenv python at $PYTHON_BIN" >&2
  exit 1
fi

rm -rf "$COVER_DIR"
mkdir -p "$COVER_DIR"

STDLIB_DIR="$("$PYTHON_BIN" -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"
PURELIB_DIR="$("$PYTHON_BIN" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
PLATLIB_DIR="$("$PYTHON_BIN" -c 'import sysconfig; print(sysconfig.get_path("platlib"))')"
IGNORE_DIRS="$STDLIB_DIR:$PURELIB_DIR:$PLATLIB_DIR"

run_tests() {
  echo
  echo "==> $*"
  "$PYTHON_BIN" "$@"
}

PYTEST_ARGS=(tests)

run_tests -m pytest "${PYTEST_ARGS[@]}"

echo
echo "==> Coverage summary"
"$PYTHON_BIN" -m trace \
  --count \
  --summary \
  --missing \
  --coverdir "$COVER_DIR" \
  --ignore-dir "$IGNORE_DIRS" \
  --module pytest "${PYTEST_ARGS[@]}" > "$REPORT_FILE"

echo
echo "==> Project coverage focus"
if command -v rg >/dev/null 2>&1; then
  rg 'leathercraft_svg|tests\.test_' "$REPORT_FILE" || true
else
  grep -E 'leathercraft_svg|tests\.test_' "$REPORT_FILE" || true
fi

echo
echo "Coverage artifacts written to $COVER_DIR (*.cover files)"
