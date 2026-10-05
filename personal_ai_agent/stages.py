"""Workflow stage definitions and placeholder executors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol


STAGE_PENDING = "pending"
STAGE_RUNNING = "running"
STAGE_COMPLETED = "completed"
STAGE_SKIPPED = "skipped"
STAGE_BLOCKED = "blocked"
STAGE_FAILED = "failed"
STAGE_AWAITING_APPROVAL = "awaiting_approval"

TERMINAL_STAGE_STATUSES = {
    STAGE_COMPLETED,
    STAGE_SKIPPED,
    STAGE_BLOCKED,
    STAGE_FAILED,
    STAGE_AWAITING_APPROVAL,
}


@dataclass(frozen=True)
class Stage:
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
    status: str
    message: str
    artifact: str | None = None


class StageExecutor(Protocol):
    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
        """Execute one stage and return its result."""


class PlaceholderStageExecutor:
    """Executor used before real AI capabilities exist."""

    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
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
    """Routes implemented stages to their executor and preserves placeholders elsewhere."""

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
        self.outcomes = outcomes or {}
        self.fallback = fallback or PlaceholderStageExecutor()
        self.calls: list[str] = []

    def execute(self, *, stage: Stage, subject: str, run_dir: Path) -> StageResult:
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
