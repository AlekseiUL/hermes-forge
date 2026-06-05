from __future__ import annotations

import json
from pathlib import Path

from hermes_forge.models import Finding
from hermes_forge.paths import write_text_under


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- Review evidence before changing anything."


def render_proposals(findings: list[Finding], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if not findings:
        prop_dir = out_dir / "prop-0001"
        prop_dir.mkdir(parents=True, exist_ok=True)
        data = {"schema_version": "hermes-forge.proposal/v1", "id": "prop-0001", "target_type": "no_change", "status": "draft", "rationale": "No actionable findings were found in the current evidence ledger.", "requires_approval": False, "auto_apply_forbidden": True, "priority_score": 0, "priority_label": "none", "diff_preview_path": "diff.preview", "eval_plan_path": "eval-plan.md", "rollback_path": "rollback.md"}
        write_text_under(prop_dir / "proposal.json", out_dir, json.dumps(data, indent=2))
        write_text_under(prop_dir / "proposal.md", out_dir, "# Proposal prop-0001\n\nNo change recommended from current evidence.\n\nThis is an explicit NO_CHANGE proposal, not a missing result.\n")
        write_text_under(prop_dir / "diff.preview", out_dir, "# NO_CHANGE\n\nNo file diff is proposed.\n")
        write_text_under(prop_dir / "eval-plan.md", out_dir, "# Eval plan for prop-0001\n\n- Verify evidence is insufficient for a change.\n- Verify privacy scan passes.\n- Verify no candidate executor should run for a NO_CHANGE proposal.\n")
        write_text_under(prop_dir / "rollback.md", out_dir, "# Rollback\n\nNo change is proposed or applied. Nothing to roll back.\n")
        written.append(prop_dir / "proposal.json")
        return written
    for idx, finding in enumerate(findings, 1):
        pid = f"prop-{idx:04d}"
        prop_dir = out_dir / pid
        prop_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": "hermes-forge.proposal/v1",
            "id": pid,
            "status": "draft",
            "target_type": "eval_candidate",
            "finding_ids": [finding.id],
            "evidence_ids": finding.evidence_ids,
            "risk": finding.severity,
            "priority_score": finding.priority_score,
            "priority_label": finding.priority_label,
            "priority_reason": finding.priority_reason,
            "review_focus": finding.review_focus,
            "next_checks": finding.next_checks,
            "requires_approval": True,
            "auto_apply_forbidden": True,
            "diff_preview_path": "diff.preview",
            "eval_plan_path": "eval-plan.md",
            "rollback_path": "rollback.md",
        }
        write_text_under(prop_dir / "proposal.json", out_dir, json.dumps(data, indent=2))
        write_text_under(prop_dir / "proposal.md", out_dir, f"# Proposal {pid}\n\n## Priority\n- label: `{finding.priority_label}`\n- score: `{finding.priority_score}`\n- reason: {finding.priority_reason}\n\n## Review focus\n{finding.review_focus}\n\n## Hypothesis\n{finding.root_cause_hypothesis}\n\n## Evidence\n{', '.join(finding.evidence_ids)}\n\n## Next checks\n{_md_list(finding.next_checks)}\n\n## Why no blind auto-apply\nForge can run only approved, registered candidate executors. Arbitrary proposal text is a review card, not an instruction to edit live Hermes files.\n")
        write_text_under(prop_dir / "diff.preview", out_dir, "# No live diff in proposal stage\n\nForge proposes review work first. Candidate apply requires a separate candidate payload, approval id, scoped live target, backup and registered executor.\n")
        write_text_under(prop_dir / "eval-plan.md", out_dir, f"# Eval plan for {pid}\n\n- Verify proposal schema and priority fields.\n- Verify evidence IDs exist in the evidence ledger.\n- Run privacy scan on generated artifacts.\n- Perform the next checks listed in `proposal.md` before any candidate apply.\n- Re-run Forge scan after any approved bounded change and compare finding count/priority.\n")
        write_text_under(prop_dir / "rollback.md", out_dir, "# Rollback\n\nProposal stage does not apply changes. If a later bounded candidate executor runs, restore from that apply output's backup manifest if rollback is needed.\n")
        written.append(prop_dir / "proposal.json")
    return written
