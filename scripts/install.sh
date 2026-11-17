#!/usr/bin/env bash
# install.sh — one-command installer for the task-router skill.
# Copies SKILL.md + scripts + references to the Claude/Codex/opencode skill dirs,
# verifies sha256 per file, proves the table loads. Idempotent. No quota cost.
# Usage: ./install.sh [--check-only] [--uninstall]
set -u
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DESTS="$HOME/.claude/skills/task-router $HOME/.codex/skills/task-router $HOME/.config/opencode/skills/task-router"
FILES="SKILL.md SETUP_PROMPT.md scripts/route.py scripts/route_exec.py scripts/size.py scripts/setup.py scripts/verify_table.py scripts/parity_check.py references/routing-table.json references/golden-set.json references/audit-schema.json references/risks.md"
CHECK_ONLY=0; UNINSTALL=0
for a in "$@"; do
  case "$a" in
    --check-only) CHECK_ONLY=1 ;;
    --uninstall) UNINSTALL=1 ;;
  esac
done
command -v python3 >/dev/null || { echo "need python3 on PATH"; exit 1; }
# shellcheck disable=SC2086
if [ "$UNINSTALL" = 1 ]; then
  for d in $DESTS; do rm -rf "$d" && echo "removed $d"; done
  exit 0
fi
ok=1
for d in $DESTS; do
  if [ "$CHECK_ONLY" = 1 ]; then
    [ -d "$d" ] || { echo "MISSING dir $d"; ok=0; continue; }
    for f in $FILES; do
      [ -f "$d/$f" ] || { echo "MISSING $d/$f"; ok=0; continue; }
      a=$(sha256sum "$SRC/$f" | cut -d' ' -f1); b=$(sha256sum "$d/$f" | cut -d' ' -f1)
      [ "$a" = "$b" ] || { echo "DIFF $d/$f"; ok=0; }
    done
    echo "checked $d"
  else
    mkdir -p "$d"
    for f in $FILES; do
      mkdir -p "$d/$(dirname "$f")"
      cp "$SRC/$f" "$d/$f"
    done
    echo "installed $d"
  fi
done
[ "$ok" = 1 ] || { echo "MISMATCHES found"; exit 1; }
if [ "$CHECK_ONLY" = 1 ]; then echo "all installs verified clean"; exit 0; fi
python3 "$SRC/scripts/route.py" --self-test
