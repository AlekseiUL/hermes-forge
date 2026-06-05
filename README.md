# Hermes Forge

Universal local-first improvement loop for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Forge helps any Hermes user answer one practical question:

> What can my agent setup improve, why, how do I prove it, and what is the safest next step?

It scans a Hermes home, collects safe evidence, groups weak signals, and produces reviewable improvement opportunities with hypotheses, experiments, success criteria and safe next steps.

It is **not autonomous self-modification**. It does not rewrite your agent by itself. `apply` is intentionally disabled in this preview.

## Why this exists

Hermes Forge is inspired by the practical idea behind evidence-driven self-improvement work: improvement should not mean blind self-editing. It should mean a controlled loop where real behavior produces observations, observations become evidence, evidence becomes an improvement candidate, and the candidate is checked before anyone applies it.

For Hermes Agent, that loop becomes:

```text
Hermes runtime -> observations -> evidence -> opportunities -> experiments -> candidates -> apply gate
```

This repository is **Anthropic-inspired**, not Anthropic-affiliated, and not an implementation of an official Anthropic system or paper. It translates the principle into a practical, local-first improvement loop for Hermes users.

## Operating flow

```text
improve --mode read-only -> evidence -> findings -> opportunities -> report -> optional gated change
```

The core idea is:

```text
found -> checked -> proposed improvement -> experiment/eval -> safe next step
```

## Who is this for?

Hermes Forge is for:

- Hermes Agent users with multiple profiles, skills, cron jobs or runtime logs;
- developers building safer agent workflows;
- teams that want evidence before changing skills, routing, tasks or automations;
- maintainers who want a repeatable improvement rhythm without silent self-modification.

It is not:

- an official Hermes Agent project;
- an Anthropic project;
- a background agent that edits itself automatically;
- a security scanner or secret collector;
- a “fix everything” button.

## What it can improve today

Forge currently finds improvement candidates from:

- profile inventory;
- skill frontmatter metadata;
- cron metadata;
- bounded log categories and safe classifiers;
- session DB aggregate metadata;
- optional Kanban SQLite aggregate metadata;
- optional existing Doctor report summaries.

Then it creates an improvement report that says: what can become better, what evidence supports it, how to test the improvement, what success looks like, and why the change must not be applied automatically.

## Quick start from source

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
hermes-forge doctor
hermes-forge capabilities
```

## One-command read-only improvement loop

Run Forge against a Hermes home without changing it:

```bash
hermes-forge improve --mode read-only --hermes-home ~/.hermes --all-profiles --out ./forge-runs/latest
```

Compare with a previous run when you have one:

```bash
hermes-forge improve --mode read-only --hermes-home ~/.hermes --all-profiles --baseline ./forge-runs/previous --out ./forge-runs/latest
```

Open:

```text
./forge-runs/latest/report.md
```

The report answers:

- what can be improved;
- why Forge thinks so;
- what evidence exists;
- what state the opportunity is in (`watch_only`, `needs_owner_decision`, `ready_for_experiment`, `ready_for_diff_preview`);
- what experiment or eval would prove the improvement;
- what typed safe next step follows (`review`, `create_eval`, `open_diff`, `ask_approval`, `no_change`);
- how this run compares with a previous baseline, if provided;
- what Forge did not touch.

Artifacts include:

- `run.json`
- `policy.json`
- `inventory.json`
- `evidence-ledger.jsonl`
- `findings.json`
- `dedup-groups.json`
- `opportunities.json`
- `proposals.json`
- `scan-summary.json`
- `baseline-comparison.json`
- `report.md`
- `redaction-report.json`

## Experiment planner

Turn one opportunity into a safe experiment plan/result without applying changes:

```bash
hermes-forge experiment --opportunity ./forge-runs/latest/opportunities.json --id opp-0001 --out ./forge-runs/experiments/opp-0001
```

For allowlisted deterministic plans only, request readiness validation:

```bash
hermes-forge experiment --opportunity ./forge-runs/latest/opportunities.json --id opp-0001 --out ./forge-runs/experiments/opp-0001 --run
```

Experiment artifacts include:

- `experiment-plan.json`
- `experiment-result.json`
- `checks.json`
- `expected-outcome.md`
- `experiment.md`

Experiment statuses:

- `PLAN_ONLY`
- `READY_TO_RUN`
- `PASSED`
- `FAILED`
- `BLOCKED_NEEDS_OWNER_CONTEXT`

`experiment` never executes arbitrary commands from an opportunity. In this release `--run` validates readiness for exact allowlisted plans; it does not shell out to the documented eval command and does not mark experiments as passed.

## Diff preview

Turn an experiment result into a preview-only change package:

```bash
hermes-forge diff-preview --experiment ./forge-runs/experiments/opp-0001 --hermes-home ~/.hermes --out ./forge-runs/diff-preview/opp-0001
```

Diff-preview artifacts include:

- `diff-preview.json`
- `diff-preview.md`
- `proposed-files.json`
- `risk-check.json`
- `rollback-plan.md`
- `tests-to-run.md`

`diff-preview` shows what kind of file/change could be prepared next, why, what tests should run, and what rollback would be needed. It does not edit files and does not apply patches.

## Low-level example flow

These commands use synthetic fixtures from this source checkout:

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_minimal --all-profiles --kanban-db tests/fixtures/kanban/kanban.db --doctor-report tests/fixtures/doctor/report.json --out /tmp/hermes-forge-scan
hermes-forge analyze --scan /tmp/hermes-forge-scan --out /tmp/hermes-forge-scan/analysis
hermes-forge propose --analysis /tmp/hermes-forge-scan/analysis --out /tmp/hermes-forge-scan/proposals
hermes-forge eval --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json --out /tmp/hermes-forge-scan/evals/prop-0001
hermes-forge apply --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json
```

For most users, start with `improve --mode read-only`; the low-level commands are kept for inspection and tooling.

Expected MVP apply result:

```json
{"status": "APPLY_DISABLED_IN_MVP"}
```

`apply` exits non-zero by design.

## Safety model

Default mode is read-only. Forge writes only under `--out`, and `--out` is blocked if it is inside the scanned Hermes home.

Forge does not:

- restart gateways;
- execute cron jobs;
- execute plugins;
- execute MCP servers;
- edit skills or memory;
- send platform messages;
- push to GitHub;
- require network access.

Session, log, skill, task and report text is treated as untrusted data, never as instructions.

See [`docs/safety-model.md`](docs/safety-model.md).

## Examples

See [`examples/`](examples/) for source-checkout examples:

- minimal Hermes fixture;
- optional Kanban metadata;
- existing Doctor report import;
- `NO_CHANGE` proposal.

## Current status

Implemented:

- CLI: `doctor`, `capabilities`, `improve`, `experiment`, `diff-preview`, `scan`, `analyze`, `propose`, `eval`, `apply`, `rollback`;
- read-only evidence adapters;
- one-shot read-only improvement loop;
- opportunity reports with hypotheses, opportunity states, structured eval plans, success criteria and typed safe next steps;
- baseline comparison between read-only `improve` runs;
- safe `experiment` planner/results between opportunity and future diff-preview;
- preview-only `diff-preview` package with proposed file shapes, risk check, tests and rollback plan;
- first-class `NO_CHANGE` proposals;
- deterministic eval plans;
- actionable proposal templates with priority, review focus and next checks;
- privacy scanner;
- synthetic fixtures and tests;
- repository-quality GitHub Actions workflow.

Known limitations:

- session DB support is metadata-only and schema-limited;
- Kanban support is optional and metadata-only;
- log taxonomy is heuristic and category-only;
- eval output is a deterministic plan, not a benchmark runner;
- `apply` is disabled in MVP.

## Canonical source

This project is maintained by Aleksei Ulianov / Sprut_AI.
Original repository: https://github.com/AlekseiUL/hermes-forge

If you found this project mirrored, repackaged, or redistributed elsewhere, check this repository as the source of truth.

## Attribution

Where permitted by the applicable license, if you reuse, fork, modify, package, or publish this work, keep the original copyright and license notice and link back to the canonical repository.

## License

MIT. See [`LICENSE`](LICENSE).
