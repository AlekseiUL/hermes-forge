# Hermes Forge

Local-first improvement control plane for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Hermes already has skills, memory, sessions, cron and profiles. Forge looks at how those pieces actually perform, collects evidence from real work, classifies repeated failures/corrections, and generates reviewable proposals with eval and rollback plans.

MVP boundary: **read-only scan/analyze/propose/eval**. `apply` is intentionally disabled.

Not autonomous self-modification. Not recursive AGI. Not an official Anthropic or Hermes Agent project.

## Why

The useful lesson from the Anthropic self-improvement discussion is not hype. It is the bottleneck shift: agents can generate more changes than humans can review calmly, so improvement needs evidence, evals, review gates and rollback.

Forge turns that into a Hermes-native loop:

```text
Hermes work -> evidence -> taxonomy -> proposal -> eval plan -> review -> apply gate -> rollback
```

## Quick start from source

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Commands

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_minimal --all-profiles --out /tmp/hermes-forge-scan
hermes-forge analyze --scan /tmp/hermes-forge-scan --out /tmp/hermes-forge-scan/analysis
hermes-forge propose --analysis /tmp/hermes-forge-scan/analysis --out /tmp/hermes-forge-scan/proposals
hermes-forge eval --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json --out /tmp/hermes-forge-scan/evals/prop-0001
hermes-forge apply --proposal /tmp/hermes-forge-scan/proposals/prop-0001/proposal.json
```

`--out` must be outside the scanned Hermes home. This is enforced so scan mode cannot write into live profile inputs.

Expected MVP apply result:

```json
{"status": "APPLY_DISABLED_IN_MVP"}
```

## Implemented now

- CLI skeleton: `scan`, `analyze`, `propose`, `eval`, `apply`, `rollback`.
- Read-only fixture scan.
- Profile/skill/cron/log collectors over synthetic Hermes homes.
- Evidence ledger JSONL.
- Findings taxonomy and Markdown report.
- Proposal artifacts with diff preview, eval plan and rollback plan.
- Disabled apply/rollback stubs.
- Redaction and path labels.
- Tests proving redaction, read-only behavior and artifact generation.

## Planned

- Session DB adapter.
- Kanban adapter.
- Doctor report adapter.
- More deterministic eval templates.
- Optional semantic judge.
- Apply executors only after separate approval and backup/rollback tests.

## Known limitations

- Phase 0 uses synthetic fixtures by default.
- No session DB adapter yet.
- No Kanban adapter yet.
- Log taxonomy is heuristic and category-only.
- Eval output is a plan, not a benchmark runner.
- `apply` is disabled in MVP.

## Safety model

Default scan is read-only. Forge writes only under `--out`. It does not restart gateways, execute cron jobs, run MCP servers, execute plugins, edit skills, edit memory, or push to GitHub.

See [`docs/safety-model.md`](docs/safety-model.md).

## License

MIT. See [`LICENSE`](LICENSE).
