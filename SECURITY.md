# Security

Do not paste raw Hermes sessions, logs, `.env`, `auth.json`, cookies, private keys, OAuth material, connection strings or full `forge-run/` artifacts into public issues.

Run the privacy scanner before sharing artifacts:

```bash
python scripts/privacy_scan.py /path/to/forge-run
```

MVP safety boundary:

- scan/analyze/propose/eval are read-only for Hermes inputs;
- output writes go only under `--out`, and `--out` is blocked when it is inside the scanned Hermes home;
- `apply` returns `APPLY_DISABLED_IN_MVP`;
- no gateway restart;
- no cron execution;
- no MCP/plugin execution;
- no live profile edits.
