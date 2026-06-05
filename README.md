# Hermes Forge

Local-first improvement control plane for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Forge helps a Hermes user answer one practical question:

> What should I improve in my agent setup, why, and how do I review it safely?

It scans a Hermes home, collects safe evidence, groups weak signals, and produces reviewable improvement proposals with eval and rollback plans.

It is **not autonomous self-modification**. It does not rewrite your agent by itself. `apply` is intentionally disabled in this preview.

## Why this exists

Hermes Forge is inspired by the same practical idea behind Anthropic-style self-improvement work: improvement should not mean blind self-editing. It should mean a controlled loop where real behavior produces evidence, evidence becomes a proposed change, and the change is checked before anyone applies it.

For Hermes Agent, that loop becomes:

```text
Hermes runtime -> evidence -> improvement proposal -> eval plan -> review -> apply gate
```

This repository is **Anthropic-inspired**, not Anthropic-affiliated, and not an implementation of an official Anthropic system or paper. It translates the principle into a practical, local-first control plane for Hermes users.


## Operating flow

```text
scan -> evidence -> findings -> proposal -> eval -> review -> apply gate -> rollback plan
```

## Who is this for?

Hermes Forge is for:

- Hermes Agent users with multiple profiles, skills, cron jobs or runtime logs;
- developers building safer agent workflows;
- teams that want evidence before changing skills, routing, tasks or automations.

It is not:

- an official Hermes Agent project;
- an Anthropic project;
- a background agent that edits itself automatically;
- a security scanner or secret collector.

## What it can improve today

Forge currently finds improvement candidates from:

- profile inventory;
- skill frontmatter metadata;
- cron metadata;
- bounded log categories;
- session DB aggregate metadata;
- optional Kanban SQLite aggregate metadata;
- optional existing Doctor report summaries.

Then it creates proposals that say: what looks weak, what evidence supports it, how to evaluate a change, and why the change must not be applied automatically.

## Quick start from source

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
hermes-forge doctor
hermes-forge capabilities
```

## Example flow

These commands use synthetic fixtures from this source checkout:

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_minimal --all-profiles --kanban-db tests/fixtures/kanban/kanban.db --doctor-report tests/fixtures/doctor/report.json --out /tmp/hermes-forge-scan
hermes-forge analyze --scan /tmp/hermes-forge-scan --out /tmp/hermes-forge-scan/analysis
hermes-forge propose --analysis /tmp/hermes-forge-scan/analysis --out /tmp/hermes-forge-scan/proposals
hermes-forge eval --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json --out /tmp/hermes-forge-scan/evals/prop-0001
hermes-forge apply --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json
```

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

- CLI: `doctor`, `capabilities`, `scan`, `analyze`, `propose`, `eval`, `apply`, `rollback`;
- read-only evidence adapters;
- first-class `NO_CHANGE` proposals;
- deterministic eval plans;
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
Original repository after publication: https://github.com/AlekseiUL/hermes-forge

## License

MIT. See [`LICENSE`](LICENSE).
