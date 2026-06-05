# Safety model

Hermes Forge treats local Hermes data as sensitive and untrusted evidence.

## Default

- Read-only collectors.
- Bounded log reads.
- Redaction before writing artifacts.
- Writes only under `--out`.
- No cron/gateway/MCP/plugin execution.
- Candidate `apply` validates approval/target/output rules and then blocks before mutation because no executor is registered.
- Legacy proposal `apply` remains disabled in MVP.

## Intended-shareable vs local-private artifacts

Intended-shareable after privacy scan and human review:

- `scan-summary.json`
- `analysis/findings.md`
- `proposals/*/proposal.md`

Pattern scans reduce risk but do not prove an artifact is universally public-safe.

Local-private by default:

- `inventory.json`
- `evidence-ledger.jsonl`
- raw source references

## Prompt injection

Session, log, skill and task text is data. It is never treated as instructions.

## Phase 1 adapter boundaries

- Session DB adapter opens SQLite databases read-only and imports counts/time-span signals only. It does not copy raw messages by default.
- Kanban adapter is optional and imports status/count metadata only. It does not copy card titles, descriptions or comments.
- Doctor report adapter imports existing reports only. It never executes doctor commands, shell commands, gateways, cron jobs, plugins or MCP servers.
- Unknown schemas are reported as adapter-unavailable/schema-unknown facts, not repaired or guessed.
