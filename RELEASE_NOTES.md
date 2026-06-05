# Release notes

## v0.1.2 — Safe log classifiers

Adds safer and more actionable runtime-log evidence:

- gateway delivery classifier with strict error-context counts;
- tool/runtime classifier with category counts, exit codes, exception class names and safe tool labels;
- `unknown/no_explicit_tool_label` when tool attribution is not explicit instead of guessing;
- regression tests proving raw log lines, command arguments, paths, chat IDs and token-shaped strings are not emitted;
- source/output privacy scans remain clean.

Safety boundary remains unchanged:

- `apply` is still disabled with `APPLY_DISABLED_IN_MVP`;
- no live Hermes edits;
- no gateway restarts;
- no cron/plugin/MCP execution.

## v0.1.1 — Actionability layer

Adds more useful improvement proposals:

- priority score and priority label for each finding;
- finding-specific review focus;
- concrete next-check steps before any change;
- richer proposal Markdown so outputs work as review cards;
- proposal JSON fields for priority/review/next checks;
- privacy scanner now skips local `.venv` environments during source-tree scans.

Safety boundary remains unchanged:

- `apply` is still disabled with `APPLY_DISABLED_IN_MVP`;
- no live Hermes edits;
- no gateway restarts;
- no cron/plugin/MCP execution.

## v0.1.0 — Safety-first preview

Hermes Forge is a local-first improvement control plane for Hermes Agent. It is Anthropic-inspired in the narrow engineering sense: evidence-backed improvement proposals, eval plans, review gates, and rollback planning instead of blind autonomous self-modification.

Included in this preview:

- read-only `scan`, `analyze`, `propose`, and `eval` flow;
- `apply` hard-disabled with `APPLY_DISABLED_IN_MVP`;
- Forge self-check via `hermes-forge doctor`;
- machine-readable capability report via `hermes-forge capabilities`;
- profile, skill, cron, bounded log, session metadata, optional Kanban metadata and existing Doctor report adapters;
- first-class `NO_CHANGE` proposals;
- synthetic examples and fixtures;
- privacy scanner and repository-quality CI.

Not included:

- automatic self-modification;
- live Hermes profile edits;
- gateway restarts;
- cron/plugin/MCP execution;
- GitHub push/release automation;
- apply executors.

Canonical source after publication:

```text
https://github.com/AlekseiUL/hermes-forge
```
