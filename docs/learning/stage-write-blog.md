# Stage Walkthrough: `write-blog`

`write-blog` turns one evidence-context package into a technical blog draft. It
does not inspect the repository, read new resources, publish content, or create
social posts.

## Where It Fits

```text
research-work -> research-report.md
research-resources -> resources-report.md
build-evidence-context -> context-brief.md
write-blog -> blog-draft.md
review-blog -> blog-review.md
```

This is the first grounded-generation stage. Research and context engineering
establish what can be said; the writer chooses a clear technical narrative from
that prepared material.

## Execution Path

`build_content_executor()` in `personal_ai_agent/cli.py` creates a
`BlogWriterExecutor` with `BlogWriterSettings`. `RoutedStageExecutor` in
`personal_ai_agent/stages.py` routes only the `write-blog` stage to it.

```text
context-brief.md
  -> collect_blog_inputs()
  -> verify a ready article focus and E/R references
  -> bounded model input
  -> OpenAIResponsesClient.generate_json()
  -> validate_blog_draft()
  -> blog-draft.md
```

The implementation lives in `personal_ai_agent/write_blog.py`. The shared
runtime still owns checkpoints, attempts, artifact validation, failure, and
resume behavior.

## Input Boundary

`collect_blog_inputs()` accepts only the current run's `context-brief.md`. It
requires the expected evidence-context header, a `ready` recommended article
focus, and at least one traceable work (`E...`) or resource (`R...`) reference.

The context brief is capped at 40 KB, read as UTF-8, and redacted again before
being sent to the model. If it is missing, malformed, too large, or does not
support a ready focus, the stage writes a visible blocked `blog-draft.md` and
returns `blocked` without calling the model.

## Grounded Generation Contract

The model returns JSON, not unconstrained Markdown. Its structure includes a
title, optional subtitle, named article sections, cited paragraphs, cited
technical takeaways, and review caveats.

Every article paragraph and takeaway must cite one or more IDs from the context
brief. `validate_blog_draft()` rejects empty citations and invented `E...` or
`R...` IDs before any draft is saved. The runtime renders the Markdown artifact
with source references, uncertainty, and `draft_for_human_review` status.

This is grounded generation: the model still chooses language and structure,
but it cannot independently reconstruct the repository story or cite evidence
that the prepared context did not supply. It reduces hallucination risk; it does
not prove the article is correct. Human review remains required.

## Outcomes

- `completed`: the context was ready, the structured draft passed validation,
  and `blog-draft.md` was saved.
- `blocked`: the writer lacks a usable, evidence-supported context. The run
  stops rather than producing an article from guesses.
- `failed`: the model request fails or returns malformed output, unknown IDs,
  or uncited article content. The runtime records the technical failure.

`completed` means the draft met its runtime contract. It does not mean it is
approved, published, or free of interpretation errors.

## Tests

`tests/test_runtime.py` proves that:

- a full research-to-context-to-blog sequence writes a cited draft;
- a missing context brief blocks without a model call; and
- a draft that cites an invented evidence ID is rejected.

The tests use `FakeModelClient`, so they test deterministic grounding rules
without an API key or a paid model request.
