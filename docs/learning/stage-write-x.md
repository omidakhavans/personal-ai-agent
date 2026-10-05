# Stage Walkthrough: `write-x`

`write-x` turns the same approved, reviewed article into either one concise X
post or a short technical thread. It writes `x-draft.md`; it does not research,
rewrite the canonical article, call an X API, schedule, or publish.

## Controlled Generation

`XWriterExecutor` uses the identical reviewed-input gate as `write-linkedin`.
The model returns a structured choice of `single` or `thread`, a rationale,
cited post text, a main insight, link placement, and human-attention notes.

The validator requires:

- exactly one post for `single`;
- two to five posts for `thread`;
- no post longer than 280 characters; and
- traceable `E...` or `R...` evidence for every post and insight.

This is controlled generation: trusted source content, platform-specific
objectives, explicit boundaries, and structured validation keep creativity
useful without letting the model invent a new version of the story.

All output remains `draft_for_review`. Human review is still required before
anything leaves the system.
