#!/usr/bin/env bash
# scan.sh — read-only secret & risky-pattern sweep for a project.
# Usage: scripts/scan.sh [project-dir]   (defaults to current dir)
# Prints findings with masked secrets. Makes NO changes and NO network calls.
set -uo pipefail
DIR="${1:-.}"
cd "$DIR" || { echo "Cannot cd into $DIR"; exit 1; }

EXCLUDE='--exclude-dir=node_modules --exclude-dir=.git --exclude-dir=build --exclude-dir=dist --exclude-dir=.next --exclude-dir=.dart_tool --exclude-dir=ios/Pods'

mask() { sed -E 's/([A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]{6,}([A-Za-z0-9_\-]{3})/\1…\2/g'; }

echo "== Security pattern sweep: $DIR =="
echo

echo "-- [1] .env files tracked by git (should usually be ignored) --"
git ls-files 2>/dev/null | grep -Ei '(^|/)\.env' || echo "  none tracked (good)"
echo

echo "-- [2] .env present but not in .gitignore --"
if [ -f .gitignore ]; then
  ls -a 2>/dev/null | grep -E '^\.env' | while read -r f; do
    grep -qF "$f" .gitignore 2>/dev/null || echo "  $f NOT in .gitignore"
  done
fi
echo

echo "-- [3] Likely hardcoded secrets (masked) --"
grep -rInE $EXCLUDE \
  -e 'sk-[A-Za-z0-9_\-]{18,}' \
  -e 'AKIA[0-9A-Z]{16}' \
  -e 'ghp_[A-Za-z0-9]{30,}' \
  -e 'AIza[0-9A-Za-z_\-]{30,}' \
  -e 'xox[baprs]-[0-9A-Za-z-]{10,}' \
  -e '-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----' \
  -e '(api[_-]?key|secret|passwd|password|token)[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{8,}' \
  . 2>/dev/null | mask | head -50 || echo "  none matched"
echo

echo "-- [4] NEXT_PUBLIC_ vars that look like secrets (shipped to browser!) --"
grep -rInE $EXCLUDE 'NEXT_PUBLIC_[A-Z_]*(SECRET|KEY|TOKEN|PASSWORD|PRIVATE)' . 2>/dev/null | mask | head -20 || echo "  none matched"
echo

echo "-- [5] Dangerous sinks --"
grep -rInE $EXCLUDE \
  -e 'dangerouslySetInnerHTML' \
  -e '\beval\(' \
  -e 'child_process' \
  -e 'new Function\(' \
  . 2>/dev/null | head -30 || echo "  none matched"
echo

echo "-- [6] Cleartext / transport security (mobile) --"
grep -rInE $EXCLUDE -e 'usesCleartextTraffic="true"' -e 'NSAllowsArbitraryLoads' . 2>/dev/null | head -10 || echo "  none matched"
echo

echo "-- [7] Permissive CORS / headers --"
grep -rInE $EXCLUDE -e 'Access-Control-Allow-Origin.{0,6}\*' -e 'cors\(\)' . 2>/dev/null | head -10 || echo "  none matched"
echo

echo "Sweep complete. This is heuristic — review hits manually, and remember"
echo "secrets in git history persist even after deletion (rotate + scrub history)."
