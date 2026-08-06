---
name: static-review
description: Use when reviewing Ruby/Rails code quality - runs the project's static-analysis battery (RuboCop, Brakeman, bundler-audit, reek, flog, flay, rubycritic, database_consistency), normalizes findings, and emits a ranked design-attention list for deeper design review
---

# Ruby Static Review

Run the static-analysis battery as **step 1** of a code-quality review.
Static output has two jobs here:

1. **Mechanical findings** — directly actionable (style, security, known CVEs,
   schema drift). Report these as-is.
2. **Design-attention list** — a ranking of files/classes most likely to reward
   a deeper design review (step 2, e.g. a POODR-based review skill).

**Prioritize, never gate.** The attention list orders the design review's
effort; it must not decide whether a file gets design review at all. Many real
design problems (misplaced responsibility, misleading naming, missing
abstraction) have no static fingerprint.

## Workflow

### 1. Detect available tools

Run `detect-tools.sh` from this skill's directory (pass the project root):

```sh
"$SKILL_DIR/detect-tools.sh" /path/to/project
```

It reports one `TOOL_<NAME>=bundled|global|missing` line per tool by
inspecting `Gemfile.lock`, then `PATH`. Run only what is present. List the
missing tools at the end of the report with a one-line "add to Gemfile
`:development` group" suggestion each — do not install or edit the Gemfile
without being asked.

### 2. Choose scope

- **Review flow** (default): the branch diff — `git diff --name-only
  <default-branch>...HEAD -- '*.rb'`. Run per-file tools on those paths only.
- **Audit flow** (when asked to audit/sweep the app): the whole project.
- Whole-app-by-nature tools always run on everything: brakeman, bundler-audit,
  database_consistency.

### 3. Run the battery

Prefer `bin/<tool>` if the project has a binstub, else `bundle exec <tool>`,
else the global tool. Use machine-readable output where the tool has it.

| Tool | Invocation | Notes |
|------|------------|-------|
| RuboCop | `rubocop --format json --force-exclusion <paths>` | Respect the project's `.rubocop.yml`; never pass `-A` in this skill |
| Brakeman | `brakeman -f json -q` | Rails apps only |
| bundler-audit | `bundle-audit check --update --format json` | Falls back to plain output on older versions |
| reek | `reek --format json <paths>` | Respect `.reek.yml` if present |
| flog | `flog -a -g <paths>` | Text output; per-method scores, `-g` groups by class |
| flay | `flay <paths>` | Text output; structural duplication mass |
| rubycritic | `rubycritic --format json --no-browser <paths>` | Wraps reek+flog+flay and adds churn×complexity — **if present, use it instead of calling those three individually** |
| database_consistency | `database_consistency` | Rails only; needs a configured dev DB |

Tools can be slow on large scopes — run independent tools in parallel, and on
audit scope warn before running rubycritic on very large apps.

### 4. Normalize and dedupe

Collect every finding into one shape:

```text
tool | file:line | check | severity | summary
```

Dedupe overlaps (RuboCop `Metrics/*` vs reek `TooManyStatements`/`LargeClass`
frequently double-report; keep one, note the corroboration — corroborated
findings rank higher).

### 5. Build the design-attention list

Rank files/classes by combined signal:

- flog total (or rubycritic complexity) — weight high
- reek smell count and severity — weight high
- flay duplication mass — medium
- churn×complexity (rubycritic only) — medium
- corroboration across tools — bonus

Map reek smells to design dimensions so the step-2 reviewer knows *why* a file
is on the list:

| reek smell | Design dimension |
|------------|------------------|
| FeatureEnvy, UtilityFunction | misplaced behavior / wrong responsibility owner |
| LargeClass, TooManyStatements, TooManyInstanceVariables | single responsibility / cohesion |
| RepeatedConditional, ControlParameter | conditional → polymorphism |
| DataClump, LongParameterList | missing abstraction / coupling |
| UncommunicativeName variants | naming / intent |

## Output contract

Report exactly two sections:

**1. Mechanical findings** — the normalized, deduped table, grouped by
severity (security and CVEs first). Only include findings; an empty section is
a normal result.

**2. Design attention** — the ranked list: `rank, file/class, signals (tool +
score), suggested dimensions`. State explicitly that the list prioritizes but
does not limit any subsequent design review. If a design-review skill is
available, hand this section to it verbatim.

Close with the missing-tools note from step 1, if any.
