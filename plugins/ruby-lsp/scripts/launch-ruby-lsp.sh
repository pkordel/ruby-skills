#!/usr/bin/env bash
# Launcher script for ruby-lsp
# Detects Ruby version manager, activates it, and runs ruby-lsp

set -euo pipefail

# Find ruby-skills detect.sh
DETECT_SCRIPT=$(ls ~/.claude/plugins/cache/*/ruby-skills/*/skills/ruby-version-manager/detect.sh 2>/dev/null | head -1)

if [[ -z "$DETECT_SCRIPT" ]]; then
    echo "Error: ruby-skills plugin not found." >&2
    echo "Install with: claude plugin install ruby-skills" >&2
    exit 1
fi

# Run detection and parse output
# Note: We can't use 'export' with sed because values may contain shell metacharacters
DETECT_OUTPUT=$("$DETECT_SCRIPT")

# Parse key variables we need (use || true to handle missing keys)
ACTIVATION_COMMAND=$(echo "$DETECT_OUTPUT" | grep "^ACTIVATION_COMMAND=" | cut -d= -f2- || true)
NEEDS_USER_CHOICE=$(echo "$DETECT_OUTPUT" | grep "^NEEDS_USER_CHOICE=" | cut -d= -f2 || true)
AVAILABLE_MANAGERS=$(echo "$DETECT_OUTPUT" | grep "^AVAILABLE_MANAGERS=" | cut -d= -f2 || true)

# Handle multiple managers case
if [[ "${NEEDS_USER_CHOICE:-}" == "true" ]]; then
    SET_PREF_SCRIPT="$(dirname "$DETECT_SCRIPT")/set-preference.sh"
    echo "Error: Multiple Ruby version managers detected: ${AVAILABLE_MANAGERS:-}" >&2
    echo "Set preference: $SET_PREF_SCRIPT <manager>" >&2
    echo "Then restart Claude Code." >&2
    exit 1
fi

# Build activation prefix
ACTIVATION="${ACTIVATION_COMMAND:-true}"

# Helper to build the full command string.
# Some version managers (rbenv, chruby, rvm) use environment-setting activation
# commands that should be chained with &&. Others (mise, asdf, shadowenv) use
# command-wrapper patterns where the target command is appended after "--".
build_cmd() {
    local cmd="$1"
    if [[ "$ACTIVATION" == *" --" ]]; then
        echo "$ACTIVATION $cmd"
    else
        echo "$ACTIVATION && $cmd"
    fi
}


# Check if ruby-lsp is installed, install if needed
# Use subshell with set +u to isolate from parent's set -u (some version managers use undefined vars)
if ! (set +u; eval "$(build_cmd 'command -v ruby-lsp')") &>/dev/null; then
    echo "ruby-lsp: Installing gem..." >&2
    if ! bash -c "$(build_cmd 'gem install ruby-lsp')" >&2; then
        echo "Error: Failed to install ruby-lsp gem" >&2
        exit 1
    fi
    echo "ruby-lsp: Installation complete." >&2
fi

# Launch ruby-lsp with version manager activation.
# For environment-setter managers, use exec to replace the bash process.
# For wrapper managers (mise, asdf), the wrapper handles process replacement.
if [[ "$ACTIVATION" == *" --" ]]; then
    exec bash -c "$(build_cmd 'ruby-lsp')"
else
    exec bash -c "$(build_cmd 'exec ruby-lsp')"
fi
