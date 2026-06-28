#!/usr/bin/env bash
#
# build-skill.sh — package a plugin's skill into a Claude.ai `.skill` bundle.
#
# A `.skill` file is just a zip whose top level contains a single folder named
# after the skill, with SKILL.md (and any resource files) inside it. The bundle
# is what Claude.ai users upload via Settings → Capabilities → Skills, and what
# we attach to a GitHub Release.
#
# Usage:
#   scripts/build-skill.sh [plugin] [skill]
#
#   plugin   plugin directory name under plugins/   (default: verifyax-api)
#   skill    skill directory name under the plugin  (default: same as plugin)
#
# Examples:
#   scripts/build-skill.sh                      # builds dist/verifyax-api.skill
#   scripts/build-skill.sh verifyax-api         # same
#
# Output: dist/<skill>.skill
#
set -euo pipefail

PLUGIN="${1:-verifyax-api}"
SKILL="${2:-$PLUGIN}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$REPO_ROOT/plugins/$PLUGIN/skills/$SKILL"
DIST_DIR="$REPO_ROOT/dist"
OUT="$DIST_DIR/$SKILL.skill"

if [[ ! -f "$SKILL_DIR/SKILL.md" ]]; then
  echo "error: $SKILL_DIR/SKILL.md not found" >&2
  echo "       expected layout: plugins/<plugin>/skills/<skill>/SKILL.md" >&2
  exit 1
fi

command -v zip >/dev/null 2>&1 || { echo "error: 'zip' is required but not installed" >&2; exit 1; }

# Read the version from the plugin's plugin.json (best-effort, for the log line).
PLUGIN_JSON="$REPO_ROOT/plugins/$PLUGIN/.claude-plugin/plugin.json"
VERSION="$(grep -oE '"version"[[:space:]]*:[[:space:]]*"[^"]+"' "$PLUGIN_JSON" 2>/dev/null | head -1 | grep -oE '[0-9][^"]*' || true)"

# Stage <skill>/ so the archive has the folder at its top level, then zip.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$SKILL_DIR" "$STAGE/$SKILL"

mkdir -p "$DIST_DIR"
rm -f "$OUT"
( cd "$STAGE" && zip -r -X "$OUT" "$SKILL" >/dev/null )

echo "Built $OUT${VERSION:+ (v$VERSION)}"
echo "Contents:"
zip -sf "$OUT" | sed 's/^/  /'
