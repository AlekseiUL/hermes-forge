# Hermes Forge examples

These examples use synthetic fixtures only. They are safe to run from a source checkout and do not require a live Hermes installation.

## Minimal Hermes fixture

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_minimal --all-profiles --out /tmp/hermes-forge-minimal
hermes-forge analyze --scan /tmp/hermes-forge-minimal --out /tmp/hermes-forge-minimal/analysis
hermes-forge propose --analysis /tmp/hermes-forge-minimal/analysis --out /tmp/hermes-forge-minimal/proposals
```

## With optional Kanban metadata

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_minimal --all-profiles --kanban-db tests/fixtures/kanban/kanban.db --out /tmp/hermes-forge-kanban
```

## With existing Doctor report import

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_minimal --all-profiles --doctor-report tests/fixtures/doctor/report.json --out /tmp/hermes-forge-doctor
```

## No-change proposal

```bash
hermes-forge scan --hermes-home tests/fixtures/hermes_home_empty --all-profiles --out /tmp/hermes-forge-no-change
hermes-forge analyze --scan /tmp/hermes-forge-no-change --out /tmp/hermes-forge-no-change/analysis
hermes-forge propose --analysis /tmp/hermes-forge-no-change/analysis --out /tmp/hermes-forge-no-change/proposals
```
