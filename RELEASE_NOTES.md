# Release notes

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
