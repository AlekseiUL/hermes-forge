from __future__ import annotations

import json
from pathlib import Path

from hermes_forge.models import Finding
from hermes_forge.paths import write_text_under


def render_proposals(findings: list[Finding], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if not findings:
        prop_dir = out_dir / "prop-0001"
        prop_dir.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": "hermes-forge.proposal/v1", "id": "prop-0001", "target_type": "no_change", "status": "draft", "requires_approval": False, "auto_apply_forbidden": True}
        write_text_under(prop_dir / "proposal.json", out_dir, json.dumps(data, indent=2))
        write_text_under(prop_dir / "proposal.md", out_dir, "# Proposal prop-0001\n\nNo change recommended from current evidence.\n")
        written.append(prop_dir / "proposal.json")
        return written
    for idx, finding in enumerate(findings, 1):
        pid = f"prop-{idx:04d}"
        prop_dir = out_dir / pid
        prop_dir.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": "hermes-forge.proposal/v1", "id": pid, "status": "draft", "target_type": "eval_candidate", "finding_ids": [finding.id], "evidence_ids": finding.evidence_ids, "risk": finding.severity, "requires_approval": True, "auto_apply_forbidden": True, "diff_preview_path": "diff.preview", "eval_plan_path": "eval-plan.md", "rollback_path": "rollback.md"}
        write_text_under(prop_dir / "proposal.json", out_dir, json.dumps(data, indent=2))
        write_text_under(prop_dir / "proposal.md", out_dir, f"# Proposal {pid}\n\n## Summary\n{finding.root_cause_hypothesis}\n\n## Evidence\n{', '.join(finding.evidence_ids)}\n\n## Why no auto-apply\nMVP apply is disabled.\n")
        write_text_under(prop_dir / "diff.preview", out_dir, "# No live diff in MVP. Review evidence and eval plan first.\n")
        write_text_under(prop_dir / "eval-plan.md", out_dir, f"# Eval plan for {pid}\n\n- Check output contract.\n- Check no private paths.\n- Re-run scan after any future manual change.\n")
        write_text_under(prop_dir / "rollback.md", out_dir, "# Rollback\n\nNo change is applied by Forge MVP. Nothing to roll back.\n")
        written.append(prop_dir / "proposal.json")
    return written
