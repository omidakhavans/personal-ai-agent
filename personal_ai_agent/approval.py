"""Explicit human checkpoint before downstream social-content drafts."""

from __future__ import annotations

from pathlib import Path

from .stages import STAGE_AWAITING_APPROVAL, Stage, StageResult


class SocialApprovalExecutor:
    """Pause a reviewed run until its owner approves social transformation."""

    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
        if stage.name != "approve-social":
            raise ValueError(f"SocialApprovalExecutor cannot execute {stage.name!r}.")
        (run_dir / stage.artifact).write_text(render_approval_request(subject), encoding="utf-8")
        return StageResult(
            STAGE_AWAITING_APPROVAL,
            "Blog review passed. Run approve-social explicitly before creating social drafts.",
            stage.artifact,
        )


def render_approval_request(subject: str) -> str:
    return "\n".join([
        "# Social Transformation Approval", "", "## Subject", "", subject, "", "## Status", "",
        "- awaiting_human_approval", "", "## Decision Required", "",
        "- Review the cited blog draft and blog review. Approve only if social drafts may be created from this version.", "",
    ])


def render_approved_social_transformations(
    subject: str, notes: str | None, blog_sha256: str
) -> str:
    details = notes.strip() if notes and notes.strip() else "No approval notes were supplied."
    return "\n".join([
        "# Social Transformation Approval", "", "## Subject", "", subject, "", "## Status", "", "- approved", "",
        "## Approved Article Identity", "", "- Article artifact: `blog-draft.md`", f"- Reviewed draft SHA-256: `{blog_sha256}`", "",
        "## Decision", "", "- Social drafts may be generated from the reviewed blog version.", "", "## Approval Notes", "", f"- {details}", "",
    ])
