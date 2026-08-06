# ruby-static-review

Static-analysis review battery for Ruby/Rails projects, as step 1 of a
two-step code-quality review:

1. **This plugin**: run the available analyzers, normalize and dedupe their
   findings, and rank the files most likely to reward deeper design review.
2. A design-review skill (e.g. a POODR-based reviewer) consumes the ranked
   design-attention list.

The core principle: static signals **prioritize** design review, they never
**gate** it. Many real design problems have no static fingerprint.

## Battery

RuboCop, Brakeman, bundler-audit, reek, flog, flay, rubycritic (used as the
single entry point for reek+flog+flay when present), database_consistency.

Only tools the project (or the machine) actually has are run;
`skills/static-review/detect-tools.sh` reports availability. The skill never
installs gems or edits the Gemfile on its own.

## Install

```bash
claude plugin install ruby-static-review@ruby-skills
```

Then ask Claude to "review code quality" or "run the static review" in a Ruby
project.
