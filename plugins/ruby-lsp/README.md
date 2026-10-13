# ruby-lsp Plugin for Claude Code

Ruby LSP integration with automatic Ruby version manager detection.

## Prerequisites

**Required** unless `ruby-lsp` is already on `PATH` (or bundled by the
project) or a devcontainer is used (see below): install the ruby-skills plugin:

```bash
claude plugin marketplace add st0012/ruby-skills
claude plugin install ruby-skills@ruby-skills
```

## Installation

```bash
claude plugin install ruby-lsp@ruby-skills
```

Claude Code turns on its LSP tool once the plugin's language server starts;
no environment variable is needed. Start a new session after installing.

## How It Works

1. **Session start:** Checks if ruby-lsp gem is installed for your project's Ruby version
2. **First LSP use:** Auto-installs ruby-lsp gem if missing (progress shown in output)
3. **Every LSP use:** Activates correct Ruby version, then runs ruby-lsp

## Devcontainers

When the project has a devcontainer config (`.devcontainer/devcontainer.json`
or `.devcontainer.json`) and its container is running, ruby-lsp runs inside
the container instead, with the project's Ruby and gems. A small proxy
(`scripts/ruby-lsp-proxy.py`) translates host paths to container paths
and back, so Claude keeps working with host paths.

- Requires the `devcontainer` CLI, `docker` and `python3` on the host, and
  `ruby-lsp` in the container (falls back to `bundle exec ruby-lsp`).
- Git worktrees work: each resolves to its own path in the container.
- Definitions inside gems point to container paths, which don't exist on the
  host.
- If the container isn't running when the session starts, the host setup
  below is used. Start the container and restart Claude Code.
- When Claude Code itself runs inside the container, there is no
  `devcontainer` CLI. Without ruby-skills, the launcher then runs the
  `ruby-lsp` on `PATH`, or `bundle exec ruby-lsp` when the project bundles it.

## Nested Git Worktrees

Git worktrees inside the checkout (for example `wt/<branch>/`) would otherwise
show every symbol once per worktree. The launcher runs ruby-lsp through
`scripts/ruby-lsp-proxy.py`, which excludes them from indexing and drops
references located in them, since ruby-lsp searches every file for references.
This applies on the host, through a devcontainer and inside a container, and
also finds worktrees whose recorded path is a host path. Without `python3`,
ruby-lsp runs directly and nothing is excluded.

## Available LSP Operations

Once the server is running, Claude can use these LSP-powered operations:

| Operation | Description |
|-----------|-------------|
| `goToDefinition` | Find where a symbol is defined |
| `findReferences` | Find all references to a symbol |
| `hover` | Get type info and documentation |
| `documentSymbol` | List all symbols in a file |
| `workspaceSymbol` | Search symbols across the project |

## Multiple Version Managers

If you have multiple Ruby version managers installed (e.g., rbenv AND chruby), you'll see a prompt to set your preference. Run:

```bash
~/.claude/plugins/cache/*/ruby-skills/*/skills/ruby-version-manager/set-preference.sh <manager>
```

Supported managers: shadowenv, chruby, rbenv, rvm, asdf, rv, mise

## Troubleshooting

### "No LSP server available"

Open `/plugin` and check the **Errors** tab, or start Claude Code with
`claude --debug` and look for `LSP server ... failed to start`. If another
enabled plugin also claims `.rb` files (such as `ruby-lsp@claude-plugins-official`),
only the first one registered is used; disable the other.

### "ruby-skills plugin not found"

Install the dependency:

```bash
claude plugin install ruby-skills@ruby-skills
```

### "Multiple version managers detected"

Set your preferred manager using the command shown in the error message, then restart Claude Code.

### LSP not responding after changing Ruby version

Restart Claude Code to re-detect the Ruby environment.

## Supported File Types

- `.rb` - Ruby files
- `.rake` - Rake task files
- `.gemspec` - Gem specifications
- `.ru` - Rack configuration
- `Rakefile` - Rake build files

## Known Issues

### LSP diagnostics only in IDE mode

Real-time diagnostics (errors/warnings as you type) are only available when running Claude Code in VS Code or Cursor. In CLI mode, Claude can use LSP operations but won't see live diagnostics.
