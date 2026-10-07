#!/usr/bin/env bash
# Shared devcontainer detection for the ruby-lsp launcher and session-start check.
# Source this file, then call devcontainer_main_folder.

# Prints the host path of the main checkout when the project has a devcontainer
# config and its container is running. Returns 1 otherwise.
devcontainer_main_folder() {
    command -v devcontainer >/dev/null 2>&1 || return 1
    command -v docker >/dev/null 2>&1 || return 1
    command -v python3 >/dev/null 2>&1 || return 1

    local main
    main=$(git worktree list --porcelain 2>/dev/null | awk 'NR == 1 { sub(/^worktree /, ""); print; exit }')
    [[ -n "$main" ]] || return 1
    main=$(cd "$main" && pwd -P) || return 1

    [[ -f "$main/.devcontainer/devcontainer.json" || -f "$main/.devcontainer.json" ]] || return 1
    [[ -n "$(docker ps -q --filter "label=devcontainer.local_folder=$main" 2>/dev/null)" ]] || return 1

    printf '%s\n' "$main"
}
