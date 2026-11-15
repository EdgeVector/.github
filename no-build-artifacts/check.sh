#!/usr/bin/env bash
# Block Cargo/Node/Python build artifacts and blobs over 2 MiB from entering git.
#
# Modes:
#   (default / --staged)  Inspect the index (pre-commit).
#   --tree [REV]          Inspect the tree at REV (default HEAD; CI).
#   --range A..B          Inspect blobs introduced by commits in the range.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

MAX_BYTES=$((2 * 1024 * 1024))

forbidden_path() {
  local p="$1"
  case "$p" in
    target/*|*/target/*) return 0 ;;
    node_modules/*|*/node_modules/*) return 0 ;;
    *.rlib|*.rmeta|*.rlib.bc|*.o) return 0 ;;
    *.pyc|__pycache__/*|*/__pycache__/*) return 0 ;;
    .fastembed_cache/*|*/.fastembed_cache/*) return 0 ;;
    */CACHEDIR.TAG|CACHEDIR.TAG) return 0 ;;
  esac
  return 1
}

MODE="staged"
RANGE=""
TREE_REV="HEAD"

while [ $# -gt 0 ]; do
  case "$1" in
    --staged) MODE="staged"; shift ;;
    --tree)
      MODE="tree"
      if [ $# -ge 2 ] && [[ "$2" != -* ]]; then TREE_REV="$2"; shift 2; else shift; fi
      ;;
    --range)
      MODE="range"
      RANGE="${2:-}"
      if [ -z "$RANGE" ]; then
        echo "lint-no-build-artifacts: --range requires A..B" >&2
        exit 2
      fi
      shift 2
      ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *)
      echo "lint-no-build-artifacts: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

offenders=()

check_path_and_size() {
  local path="$1"
  local size="$2"
  if forbidden_path "$path"; then
    offenders+=("FORBIDDEN_PATH  $path")
    return
  fi
  if [ -n "$size" ] && [ "$size" -gt "$MAX_BYTES" ] 2>/dev/null; then
    offenders+=("OVERSIZE(${size}B > ${MAX_BYTES}B)  $path")
  fi
}

case "$MODE" in
  staged)
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      mode="${line%%$'\t'*}"
      rest="${line#*$'\t'}"
      case "$mode" in
        R*|C*) path="${rest##*$'\t'}" ;;
        D*) continue ;;
        *) path="$rest" ;;
      esac
      [ -z "$path" ] && continue
      size=""
      if oid=$(git rev-parse --verify ":$path" 2>/dev/null); then
        size=$(git cat-file -s "$oid" 2>/dev/null || true)
      elif [ -f "$path" ]; then
        size=$(wc -c <"$path" | tr -d ' ')
      fi
      check_path_and_size "$path" "$size"
    done < <(git diff --cached --name-status --diff-filter=ACMR || true)
    ;;
  tree)
    while IFS=$'\t' read -r meta path; do
      [ -z "${path:-}" ] && continue
      size="${meta##* }"
      [ "$size" = "-" ] && continue
      check_path_and_size "$path" "$size"
    done < <(git ls-tree -r -l "$TREE_REV")
    ;;
  range)
    if [[ "$RANGE" == *..* ]]; then
      a="${RANGE%%..*}"
      b="${RANGE##*..}"
      if [ -z "$a" ] || [[ "$a" =~ ^0+$ ]]; then
        rev_list_args=("$b")
      else
        rev_list_args=("${a}..${b}")
      fi
    else
      rev_list_args=("$RANGE")
    fi
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      otype=$(printf '%s' "$line" | awk '{print $1}')
      [ "$otype" = "blob" ] || continue
      osize=$(printf '%s' "$line" | awk '{print $3}')
      path=$(printf '%s' "$line" | awk '{print substr($0, index($0,$4))}')
      [ -z "$path" ] && continue
      check_path_and_size "$path" "$osize"
    done < <(
      git rev-list --objects "${rev_list_args[@]}" \
        | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)'
    )
    ;;
esac

if [ "${#offenders[@]}" -gt 0 ]; then
  echo "lint-no-build-artifacts: blocked ${#offenders[@]} path(s)." >&2
  echo "lint-no-build-artifacts: build caches and files >${MAX_BYTES} bytes must not enter git." >&2
  n=0
  for o in "${offenders[@]}"; do
    n=$((n + 1))
    if [ "$n" -le 40 ]; then
      echo "  $o" >&2
    fi
  done
  if [ "${#offenders[@]}" -gt 40 ]; then
    echo "  ... and $((${#offenders[@]} - 40)) more" >&2
  fi
  exit 1
fi
exit 0
