# Safety model

Hermes Forge treats local Hermes data as sensitive and untrusted evidence.

## Default

- Read-only collectors.
- Bounded log reads.
- Redaction before writing artifacts.
- Writes only under `--out`.
- No cron/gateway/MCP/plugin execution.
- `apply` disabled in MVP.

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
