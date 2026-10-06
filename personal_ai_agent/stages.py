"""Workflow stage definitions and executor contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

type StageStatus = Literal[
    "pending",
    "running",
    "completed",
    "skipped",
    "blocked",
    "failed",
    "awaiting_approval",
]

STAGE_PENDING: StageStatus = "pending"
STAGE_RUNNING: StageStatus = "running"
STAGE_COMPLETED: StageStatus = "completed"
STAGE_SKIPPED: StageStatus = "skipped"
STAGE_BLOCKED: StageStatus = "blocked"
STAGE_FAILED: StageStatus = "failed"
STAGE_AWAITING_APPROVAL: StageStatus = "awaiting_approval"

TERMINAL_STAGE_STATUSES: frozenset[StageStatus] = frozenset({
    STAGE_COMPLETED,
    STAGE_SKIPPED,
    STAGE_BLOCKED,
    STAGE_FAILED,
    STAGE_AWAITING_APPROVAL,
})


@dataclass(frozen=True)
class Stage:
    """A named workflow step with one required artifact and Phase 1 reference."""

    name: str
    artifact: str
    phase1_skill: str


WORKFLOW_STAGES: tuple[Stage, ...] = (
    Stage("research-work", "research-report.md", "tech-research-work"),
    Stage("research-resources", "resources-report.md", "research-resources"),
    Stage("build-evidence-context", "context-brief.md", "build-evidence-context"),
    Stage("write-blog", "blog-draft.md", "write-blog"),
    Stage("review-blog", "blog-review.md", "review-blog"),
    Stage("approve-social", "approval.md", "human-approval"),
    Stage("write-linkedin", "linkedin-draft.md", "write-linkedin"),
    Stage("write-x", "x-draft.md", "write-x"),
)


@dataclass(frozen=True)
class StageResult:
    """The terminal outcome returned by an executor after one stage attempt."""

    status: StageStatus
    message: str
    artifact: str | None = None


class StageExecutor(Protocol):
    """Interface implemented by every stage capability or deterministic test double."""

    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
        """Execute one stage and return its result."""


class PlaceholderStageExecutor:
    """Deterministic fallback used by focused runtime tests.

    The production CLI routes every workflow stage to a real executor. Keeping
    this fallback makes state-machine tests independent from model calls.
    """

    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
        """Create a predictable placeholder artifact for the requested stage."""
        artifact_path = run_dir / stage.artifact
        artifact_path.write_text(
            "\n".join(
                [
                    f"# {stage.name}",
                    "",
                    f"Subject: {subject}",
                    "",
                    "Status: placeholder execution",
                    "",
                    (
                        "This stage will later be replaced with the real "
                        "AI-powered capability."
                    ),
                    "",
                    f"Phase 1 reference skill: `{stage.phase1_skill}`",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return StageResult(
            status=STAGE_COMPLETED,
            message="Placeholder stage completed.",
            artifact=stage.artifact,
        )


class RoutedStageExecutor:
    """Route each named workflow stage to its dedicated capability."""

    def __init__(
        self,
        *,
        research_work: StageExecutor,
        research_resources: StageExecutor | None = None,
        evidence_context: StageExecutor | None = None,
        write_blog: StageExecutor | None = None,
        review_blog: StageExecutor | None = None,
        approve_social: StageExecutor | None = None,
        write_linkedin: StageExecutor | None = None,
        write_x: StageExecutor | None = None,
        fallback: StageExecutor | None = None,
    ) -> None:
        """Register the concrete executor available for each workflow stage."""
        self.research_work = research_work
        self.research_resources = research_resources
        self.evidence_context = evidence_context
        self.write_blog = write_blog
        self.review_blog = review_blog
        self.approve_social = approve_social
        self.write_linkedin = write_linkedin
        self.write_x = write_x
        self.fallback = fallback or PlaceholderStageExecutor()

    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
        """Delegate execution to the stage-specific executor or test fallback."""
        if stage.name == "research-work":
            return self.research_work.execute(stage=stage, subject=subject, run_dir=run_dir)
        if stage.name == "research-resources" and self.research_resources:
            return self.research_resources.execute(stage=stage, subject=subject, run_dir=run_dir)
        if stage.name == "build-evidence-context" and self.evidence_context:
            return self.evidence_context.execute(stage=stage, subject=subject, run_dir=run_dir)
        if stage.name == "write-blog" and self.write_blog:
            return self.write_blog.execute(stage=stage, subject=subject, run_dir=run_dir)
        if stage.name == "review-blog" and self.review_blog:
            return self.review_blog.execute(stage=stage, subject=subject, run_dir=run_dir)
        if stage.name == "approve-social" and self.approve_social:
            return self.approve_social.execute(stage=stage, subject=subject, run_dir=run_dir)
        if stage.name == "write-linkedin" and self.write_linkedin:
            return self.write_linkedin.execute(stage=stage, subject=subject, run_dir=run_dir)
        if stage.name == "write-x" and self.write_x:
            return self.write_x.execute(stage=stage, subject=subject, run_dir=run_dir)
        return self.fallback.execute(stage=stage, subject=subject, run_dir=run_dir)


class MappingStageExecutor:
    """Test helper executor that can override stage outcomes."""

    def __init__(
        self,
        outcomes: Mapping[str, StageResult] | None = None,
        fallback: StageExecutor | None = None,
    ) -> None:
        """Store deterministic per-stage outcomes for state-machine tests."""
        self.outcomes = outcomes or {}
        self.fallback = fallback or PlaceholderStageExecutor()
        self.calls: list[str] = []

    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
        """Record the call and return an override or fallback stage result."""
        self.calls.append(stage.name)
        outcome = self.outcomes.get(stage.name)
        if outcome is None:
            return self.fallback.execute(stage=stage, subject=subject, run_dir=run_dir)

        if outcome.artifact:
            (run_dir / outcome.artifact).write_text(
                "\n".join(
                    [
                        f"# {stage.name}",
                        "",
                        f"Subject: {subject}",
                        "",
                        f"Status: {outcome.status}",
                        "",
                        outcome.message,
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        return outcome
