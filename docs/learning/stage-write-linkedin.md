# Stage Walkthrough: `write-linkedin`

`write-linkedin` transforms an approved, reviewed technical article into one
LinkedIn draft. It reads `blog-draft.md`, `blog-review.md`, and `approval.md`,
then writes `linkedin-draft.md`.

## Input Gate

`collect_approved_article_inputs()` requires all of the following:

- the blog remains a draft in the expected format;
- the review says `ready_for_human_review`;
- the review's SHA-256 matches the current blog bytes; and
- `approval.md` records an explicit human approval.

If any condition fails, the stage writes a readable blocked artifact without
calling the model.

## Transformation Contract

`LinkedInWriterExecutor` in `personal_ai_agent/social_writing.py` receives the
reviewed blog and review, not the repository or raw resources. Its structured
output contains short post paragraphs, a link-placement suggestion, one main
technical insight, evidence IDs, and human-attention notes.

The runtime validates every paragraph's evidence IDs before it renders the
draft. It does not use a LinkedIn API and never posts content.

This demonstrates content transformation rather than story reconstruction. The
canonical article carries the researched story; the platform stage adapts its
presentation while inheriting its claim boundaries.
