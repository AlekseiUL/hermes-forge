# Release notes

## v0.5.0 — Candidate patch preview

Adds the next safe step inside `diff-preview`: a review-only candidate unified diff.

Included:

- `diff-preview` now writes `candidate-patch.json`, `candidate.diff`, and `approval-checklist.md`;
- ready experiments produce a unified diff against a virtual candidate path such as `hermes-forge-candidates/<opportunity>/<target>.md`;
- blocked/plan-only experiments produce `NO_CANDIDATE_PATCH` instead of a misleading empty change;
- candidate patch artifacts keep `files_changed: 0`, `apply_enabled: false`, and `live_path: null`;
- Markdown/diff artifacts are rendered from redacted payloads only;
- README documents the candidate patch boundary.

Safety boundary remains unchanged:

- `apply` is still disabled with `APPLY_DISABLED_IN_MVP`;
- candidate diffs are review artifacts only;
- no live Hermes edits;
- no patch application;
- no gateway restarts;
- no cron/plugin/MCP execution;
- no platform messages;
- no raw logs, command args, chat IDs, secrets or session transcripts are exported.

## v0.4.0 — Preview-only diff package

Adds the next safe step after `experiment`: creating a reviewable diff-preview package without changing files.

Included:

- new `hermes-forge diff-preview` command;
- accepts an experiment output directory, `experiment-result.json`, or `experiment-plan.json`;
- writes `diff-preview.json`, `diff-preview.md`, `proposed-files.json`, `risk-check.json`, `rollback-plan.md`, and `tests-to-run.md`;
- classifies blocked experiments as `BLOCKED_NEEDS_OWNER_CONTEXT`, plan-only experiments as `PLAN_ONLY`, and ready experiments as `PREVIEW_ONLY`;
- proposed files use target kinds and path policies only, not live writable paths;
- rollback and tests are written as review plans, not executed.

Safety boundary remains unchanged:

- `apply` is still disabled with `APPLY_DISABLED_IN_MVP`;
- diff-preview writes only under `--out`;
- `--out` inside the scanned Hermes home is blocked;
- no live Hermes edits;
- no patch application;
- no gateway restarts;
- no cron/plugin/MCP execution;
- no platform messages;
- no raw logs, command args, chat IDs, secrets or session transcripts are exported.

## v0.3.0 — Safe experiment planner

Adds the next safe step after `improve`: turning one opportunity into a reviewable experiment plan/result without applying changes.

Included:

- new `hermes-forge experiment` command;
- accepts `opportunities.json`, `proposals.json`, or a single opportunity JSON object;
- writes `experiment-plan.json`, `experiment-result.json`, `checks.json`, `expected-outcome.md`, and `experiment.md`;
- experiment statuses: `PLAN_ONLY`, `READY_TO_RUN`, `PASSED`, `FAILED`, `BLOCKED_NEEDS_OWNER_CONTEXT`;
- `--run` validates readiness only for exact allowlisted deterministic plans and never executes arbitrary commands from opportunity data;
- owner-decision and diff-preview opportunities are blocked with `BLOCKED_NEEDS_OWNER_CONTEXT` instead of pretending to run;
- regression tests cover blocked, ready and run paths.

Safety boundary remains unchanged:

- `apply` is still disabled with `APPLY_DISABLED_IN_MVP`;
- experiment writes only under `--out`;
- no live Hermes edits;
- no gateway restarts;
- no cron/plugin/MCP execution;
- no arbitrary shell execution from opportunity fields;
- no false `PASSED` status without a real built-in runner;
- no raw logs, command args, chat IDs, secrets or session transcripts are exported.

## v0.2.1 — Improvement states and baseline comparison

Tightens the read-only improvement loop so reports are easier to act on without implying autonomous fixes:

- each opportunity now has `opportunity_state` (`watch_only`, `needs_owner_decision`, `ready_for_experiment`, `ready_for_diff_preview`);
- each opportunity has `safe_next_step_type` (`review`, `create_eval`, `open_diff`, `ask_approval`, `no_change`);
- each opportunity carries a structured `eval_plan` with command, fixture, success signal and no-live-write flags;
- new `--baseline` option for comparing a run against a previous `improve` output directory or `scan-summary.json`;
- new `baseline-comparison.json` artifact and report section;
- README documents the comparison workflow and new artifacts.

Safety boundary remains unchanged:

- `apply` is still disabled with `APPLY_DISABLED_IN_MVP`;
- read-only improve mode writes only under `--out`;
- `--out` under the scanned Hermes home is blocked;
- no live Hermes edits;
- no gateway restarts;
- no cron/plugin/MCP execution.

## v0.2.0 — Universal read-only improvement loop

Adds the first product-level auto-improvement loop for Hermes installations:

- new `hermes-forge improve --mode read-only` command;
- one-shot flow from safe collection to evidence, findings, opportunities and human report;
- improvement opportunities with hypotheses, experiments, success criteria and safe next steps;
- universal roles (`system_owner`, `reviewer`, `implementer`, `approver`) instead of internal team roles;
- new artifacts: `run.json`, `policy.json`, `opportunities.json`, `proposals.json`, `report.md`;
- no-write/no-raw-log/no-secret regression tests for the improvement loop;
- README now leads with the universal improvement loop instead of a repair-only diagnostic flow.

Safety boundary remains unchanged:

- `apply` is still disabled with `APPLY_DISABLED_IN_MVP`;
- read-only improve mode writes only under `--out`;
- `--out` under the scanned Hermes home is blocked;
- no live Hermes edits;
- no gateway restarts;
- no cron/plugin/MCP execution.

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
