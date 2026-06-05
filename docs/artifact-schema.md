# Artifact schema

Every JSON artifact carries `schema_version`.

Current schema versions:

- inventory: `hermes-forge.inventory/v1`
- evidence item: `hermes-forge.evidence/v1`
- findings: `hermes-forge.findings/v1`
- proposal: `hermes-forge.proposal/v1`
- eval plan: `hermes-forge.eval-plan/v1`

## Adapter status

`scan-summary.json` includes an `adapters` object with `enabled`, `not_configured`, or skipped/unavailable facts. Optional adapters such as Kanban and Doctor reports are not required for stock Hermes users.

`target_type: no_change` is a first-class proposal artifact. It includes `proposal.json`, `proposal.md`, `diff.preview`, `eval-plan.md`, and `rollback.md`.
