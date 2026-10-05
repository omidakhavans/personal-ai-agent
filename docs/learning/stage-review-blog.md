# Stage Walkthrough: `review-blog`

`review-blog` is the quality gate between a grounded blog draft and any
platform-specific transformation. It reads `blog-draft.md` and
`context-brief.md`, then writes `blog-review.md`. It does not rewrite the
article, research new sources, publish, or create social posts.

## Execution Path

`BlogReviewerExecutor` in `personal_ai_agent/review_blog.py` receives bounded
prior artifacts through `collect_article_inputs()` in
`personal_ai_agent/content_artifacts.py`.

```text
context-brief.md + blog-draft.md
  -> SHA-256 article identity
  -> bounded structured review
  -> validated findings
  -> blog-review.md
```

The review records the exact hash of the blog draft it inspected. Later stages
refuse a review whose hash does not match the current article. This prevents a
quietly edited article from borrowing the approval of an earlier version.

## Evaluation, Not Generation

The model returns an assessment, an approval status, findings, and caveats.
Each finding has a severity, category, exact article excerpt, evidence IDs when
support exists, and a recommended change. Application code verifies the quoted
excerpt is present in the saved blog and rejects invented evidence IDs.

`Critical` findings and material `Important` grounding or technical findings
require `needs_revision`, which blocks the run before social drafting. A passing
review receives `ready_for_human_review`; it is not a promise that the article
is objectively correct.

This is the evaluator pattern: generation and evaluation have different jobs.
Using the same prepared evidence during evaluation makes the check more useful,
but an LLM review is still fallible. Human technical review remains necessary.

## Outcomes

- `completed`: the review is `ready_for_human_review` and is fingerprinted.
- `blocked`: required input is missing, stale, malformed, or needs revision.
- `failed`: a model or output-contract error occurred.

The focused tests prove a cited review is saved, a material finding blocks the
pipeline, and stale review fingerprints cannot be used for derivatives.
