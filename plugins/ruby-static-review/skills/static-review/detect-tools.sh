#!/usr/bin/env bash
# Detect which static-analysis tools are available to a Ruby project.
# Usage: detect-tools.sh [project_root]
# Output: one TOOL_<NAME>=bundled|global|missing line per tool.
#   bundled  - present in the project's Gemfile.lock (run via bin/ or bundle exec)
#   global   - not in the bundle, but an executable is on PATH
#   missing  - not available
set -euo pipefail

root="${1:-.}"
lockfile="$root/Gemfile.lock"

# tool-key:gem-name:executable
tools="
RUBOCOP:rubocop:rubocop
BRAKEMAN:brakeman:brakeman
BUNDLER_AUDIT:bundler-audit:bundle-audit
REEK:reek:reek
FLOG:flog:flog
FLAY:flay:flay
RUBYCRITIC:rubycritic:rubycritic
DATABASE_CONSISTENCY:database_consistency:database_consistency
"

for entry in $tools; do
  key="${entry%%:*}"
  rest="${entry#*:}"
  gem="${rest%%:*}"
  exe="${rest#*:}"

  if [ -f "$lockfile" ] && grep -Eq "^    ${gem} \(" "$lockfile"; then
    echo "TOOL_${key}=bundled"
  elif command -v "$exe" >/dev/null 2>&1; then
    echo "TOOL_${key}=global"
  else
    echo "TOOL_${key}=missing"
  fi
done

# Context signals the skill uses to pick scope and skip Rails-only tools.
if [ -f "$lockfile" ] && grep -Eq "^    rails \(" "$lockfile"; then
  echo "PROJECT_RAILS=true"
else
  echo "PROJECT_RAILS=false"
fi
