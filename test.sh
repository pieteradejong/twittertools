#!/usr/bin/env bash
# Test runner for twittertools.
#
#   ./test.sh              unit tests in tests/ (fast, no network, no creds)
#   ./test.sh all          unit tests + legacy root-level test_*.py scripts
#   ./test.sh legacy       only the legacy root-level scripts
#   ./test.sh archives     only the archive-layout guards
#   ./test.sh db           only the archive.db tests (tests/test_archive_db.py)
#   ./test.sh consolidate  only the archive dedup tests (tests/test_consolidate_archives.py)
#   ./test.sh lint         ruff + black --check (advisory, never fails the run)
#   ./test.sh ci           unit tests + lint, lint advisory
#
# Anything after the command is passed through to pytest, e.g.
#   ./test.sh -k glob -x
#   ./test.sh all -q
set -euo pipefail

cd "$(dirname "$0")"

VENV="venv"
PY="$VENV/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "error: $PY not found. Run ./init.sh first." >&2
  exit 1
fi

if ! "$PY" -c "import pytest" 2>/dev/null; then
  echo "error: pytest not installed in $VENV. Run: $VENV/bin/pip install -r requirements.txt" >&2
  exit 1
fi

CMD="${1:-unit}"
[[ $# -gt 0 ]] && shift || true

# Legacy root-level test_*.py predate tests/ and are ad-hoc scripts with
# __main__ blocks; some need X API credentials. Kept out of the default run so
# `./test.sh` stays fast, offline and green.
LEGACY=(
  test_account_classification.py
  test_cache.py
  test_enrichment.py
  test_list_members.py
  test_profile_links.py
  test_semantic_classification.py
  test_topic_analysis.py
)

run_unit() {
  echo "==> unit tests (tests/)"
  "$PY" -m pytest tests/ -p no:warnings "$@"
}

run_legacy() {
  echo "==> legacy root-level scripts (may need X API credentials)"
  local present=()
  for f in "${LEGACY[@]}"; do [[ -f $f ]] && present+=("$f"); done
  if [[ ${#present[@]} -eq 0 ]]; then
    echo "    none present, skipping"
    return 0
  fi
  "$PY" -m pytest "${present[@]}" -p no:warnings "$@"
}

run_lint() {
  echo "==> lint (advisory)"
  local rc=0
  if "$PY" -m ruff --version >/dev/null 2>&1; then
    "$PY" -m ruff check src scripts tests || rc=1
  else
    echo "    ruff not installed, skipping"
  fi
  if "$PY" -m black --version >/dev/null 2>&1; then
    "$PY" -m black --check src scripts tests || rc=1
  else
    echo "    black not installed, skipping"
  fi
  [[ $rc -eq 0 ]] || echo "    lint reported issues (not failing the run; fix with: $PY -m black src scripts tests && $PY -m ruff check --fix src scripts tests)"
  return 0
}

case "$CMD" in
  unit)     run_unit "$@" ;;
  archives) "$PY" -m pytest tests/test_archive_layout.py -p no:warnings "$@" ;;
  db)       "$PY" -m pytest tests/test_archive_db.py -p no:warnings "$@" ;;
  consolidate) "$PY" -m pytest tests/test_consolidate_archives.py -p no:warnings "$@" ;;
  legacy)   run_legacy "$@" ;;
  lint)     run_lint ;;
  all)      run_unit "$@"; echo; run_legacy "$@" ;;
  ci)       run_unit "$@"; echo; run_lint ;;
  -*)       run_unit "$CMD" "$@" ;;
  *)        echo "unknown command: $CMD" >&2; sed -n '2,15p' "$0" >&2; exit 2 ;;
esac
