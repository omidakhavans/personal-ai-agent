"""Validated inputs shared by article review and social transformation stages."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


MAX_CONTEXT_BRIEF_CHARACTERS = 40_000
MAX_BLOG_DRAFT_CHARACTERS = 80_000
MAX_BLOG_REVIEW_CHARACTERS = 80_000


class ArtifactInputError(RuntimeError):
    """A prior run artifact is missing, stale, or unsuitable for the next stage."""


@dataclass(frozen=True)
class ArticleInputs:
    context_brief: str
    blog_draft: str
    blog_sha256: str
    work_references: dict[str, str]
    resource_references: dict[str, str]


@dataclass(frozen=True)
class ReviewedArticleInputs:
    article: ArticleInputs
    blog_review: str
    review_status: str


def collect_article_inputs(run_dir: Path) -> ArticleInputs:
    context_brief = _read_artifact(
        run_dir, "context-brief.md", MAX_CONTEXT_BRIEF_CHARACTERS
    )
    blog_draft = _read_artifact(run_dir, "blog-draft.md", MAX_BLOG_DRAFT_CHARACTERS)
    if not context_brief.startswith("# Evidence Context Brief"):
        raise ArtifactInputError("context-brief.md does not have the expected evidence-context format.")
    if not blog_draft.startswith("# Blog Draft") or "- draft_for_human_review" not in blog_draft:
        raise ArtifactInputError("blog-draft.md does not have the expected draft format.")

    work_references = extract_references(context_brief, "Work evidence", "E")
    resource_references = extract_references(context_brief, "External resource", "R")
    if not (work_references or resource_references):
        raise ArtifactInputError("Evidence context has no traceable work or resource references.")
    return ArticleInputs(
        context_brief=context_brief,
        blog_draft=blog_draft,
        blog_sha256=sha256_text(blog_draft),
        work_references=work_references,
        resource_references=resource_references,
    )


def collect_reviewed_article_inputs(run_dir: Path) -> ReviewedArticleInputs:
    article = collect_article_inputs(run_dir)
    review = _read_artifact(run_dir, "blog-review.md", MAX_BLOG_REVIEW_CHARACTERS)
    if not review.startswith("# Blog Review"):
        raise ArtifactInputError("blog-review.md does not have the expected review format.")
    fingerprint = re.search(r"^- SHA-256: `([a-f0-9]{64})`$", review, flags=re.MULTILINE)
    if not fingerprint or fingerprint.group(1) != article.blog_sha256:
        raise ArtifactInputError("blog-review.md does not match the current blog-draft.md fingerprint.")
    status = re.search(
        r"^## Approval Status\s*$\n+^- (needs_revision|ready_for_human_review)$",
        review,
        flags=re.MULTILINE,
    )
    if not status:
        raise ArtifactInputError("blog-review.md does not contain a valid approval status.")
    if status.group(1) != "ready_for_human_review":
        raise ArtifactInputError("blog-review.md requires revision before social drafts can be generated.")
    return ReviewedArticleInputs(article=article, blog_review=review, review_status=status.group(1))


def collect_approved_article_inputs(run_dir: Path) -> ReviewedArticleInputs:
    inputs = collect_reviewed_article_inputs(run_dir)
    approval = _read_artifact(run_dir, "approval.md", 12_000)
    approved = re.search(r"^## Status\s*$\n+^- approved$", approval, flags=re.MULTILINE)
    if not approval.startswith("# Social Transformation Approval") or not approved:
        raise ArtifactInputError("approval.md does not record explicit social-transformation approval.")
    fingerprint = re.search(r"^- Reviewed draft SHA-256: `([a-f0-9]{64})`$", approval, flags=re.MULTILINE)
    if not fingerprint or fingerprint.group(1) != inputs.article.blog_sha256:
        raise ArtifactInputError("approval.md does not match the current reviewed blog-draft.md fingerprint.")
    return inputs


def extract_references(report: str, label: str, prefix: str) -> dict[str, str]:
    pattern = re.compile(rf"^- {re.escape(label)} `({prefix}\d+)`: (.+)$", re.MULTILINE)
    return {identifier: reference for identifier, reference in pattern.findall(report)}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_artifact(run_dir: Path, name: str, limit: int) -> str:
    path = run_dir / name
    if not path.is_file():
        raise ArtifactInputError(f"{name} is missing.")
    if path.stat().st_size > limit:
        raise ArtifactInputError(f"{name} exceeds the {limit} byte limit.")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ArtifactInputError(f"{name} is not readable UTF-8 text.") from exc
