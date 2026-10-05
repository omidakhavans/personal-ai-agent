# Phase 2 Roadmap

## Phase 2 Goal

Rebuild the Phase 1 Content Agent outside Codex using a small, understandable local runtime and raw model APIs over time.

Phase 1 reference:

```text
tech-content-agent -> Codex Skills behavioral specification
```

Phase 2 implementation:

```text
personal-ai-agent -> custom runtime and eventually real AI capabilities
```

## Step 1: Minimal Runtime Skeleton

Status: Complete.

Implemented:

- CLI entrypoint with `run`, `resume`, `approve-social`, and `show-state`.
- Unique run ids.
- Run directories under `runs/<run-id>/`.
- Machine-readable `state.json`.
- Sequential stage orchestration.
- Placeholder stage executor.
- Markdown artifacts for each stage.
- State persistence after every transition.
- Distinction between `failed`, `blocked`, and `awaiting_approval`.
- Resume behavior that avoids rerunning completed stages.
- Tests for creation, state initialization, stage progression, artifacts, persistence, failed behavior, blocked behavior, resume behavior, and completed-stage reuse.

Current implemented workflow:

```text
subject
  -> research-work
  -> research-resources
  -> build-evidence-context
  -> write-blog
  -> review-blog
  -> approve-social
  -> write-linkedin
  -> write-x
```

## Step 2: Grounded `research-work`

Status: Complete.

Implemented:

- A read-only, configured repository input for new runs.
- Narrow local evidence collection from subject-matched text files and scoped Git metadata.
- A raw, SDK-free OpenAI Responses API client.
- Structured JSON output validation before report rendering.
- Traceable evidence identifiers in `research-report.md`.
- An explicit `blocked` result when no local evidence matches the subject.
- Persisted non-secret run inputs so an incomplete run can be resumed.

The model has no direct repository access. Application code collects the small
evidence bundle first, then the model interprets that bundle. This is the first
practical grounding boundary in the custom runtime.

## Step 3: Grounded `research-resources`

Status: Complete.

Implemented:

- Explicit `--resource` inputs for local text paths and HTTP(S) URLs.
- Bounded resource reads, including direct public GitHub repository README support.
- A `resources-report.md` contract with traceable resource IDs.
- A `skipped` result when no optional resources were supplied.
- A `blocked` result when supplied resources are all inaccessible.
- Shared raw model client and structured-output validation with the first stage.

The runtime does not independently discover web resources in V1. That is an
intentional safety and scope boundary: resource research starts from sources the
user chose, rather than a model-selected web search.

## Step 4: Grounded `build-evidence-context`

Status: Complete.

Implemented:

- Context input reads from the current run's `research-report.md` and optional
  `resources-report.md` only.
- Extracted work (`E…`) and resource (`R…`) IDs from those reports.
- A compact, structured `context-brief.md` with claim labels and source links.
- Validation that prevents invented evidence IDs and requires both source types
  for work-resource connections.
- A `blocked` result when work research is missing or when the model cannot
  recommend an evidence-supported article focus.
- A work-only brief with an explicit limitation when resource research is absent.

This is the first context-engineering stage. It reduces and structures prior
research before later generation, rather than asking a writer to recover the
important facts from every raw artifact.

## Step 5: Grounded `write-blog`

Status: Complete.

Implemented:

- Input reads only from the current run's `context-brief.md`.
- A ready article focus and traceable `E...` or `R...` references are required
  before the writer can call a model.
- The raw model client returns a structured draft: title, subtitle, sections,
  cited paragraphs, cited takeaways, and review caveats.
- Validation rejects empty citations and IDs that the context brief did not
  supply.
- The runtime renders `blog-draft.md` with evidence references, uncertainty,
  and `draft_for_human_review` status.
- A missing, malformed, oversized, or insufficient context brief produces a
  visible blocked artifact rather than an invented article.

This is grounded generation. The model has creative responsibility for article
structure and explanation, while application code constrains it to a prepared,
traceable context package. A completed draft is not publication approval.

## Learning Documentation

The current Phase 2 learning sequence lives in `docs/learning/README.md`.
It starts with the end-to-end build guide, then moves into the runtime and stage
walkthroughs. Keep a new stage walkthrough beside every future real capability.

## Step 6: `review-blog`

Status: Complete.

Implemented:

- Bounded blog and context inputs with a SHA-256 identity for the reviewed draft.
- Structured factual, technical, and editorial findings with exact article
  excerpts and traceable evidence IDs.
- A deterministic `needs_revision` gate for Critical and material Important
  factual or technical findings.
- A visible `blog-review.md`; review never silently rewrites the article.

This is an evaluator pattern. A review can improve reliability, but it is not
proof of correctness; human review remains necessary.

## Step 7: Social Approval And Transformation

Status: Complete.

Implemented:

- An `approve-social` state that pauses after a passing blog review.
- An explicit CLI approval command that records the owner's decision before
  continuing.
- LinkedIn and X transformations that require an approved, fingerprint-matched
  reviewed blog.
- Structured social outputs with evidence IDs; X validates a single post or a
  two-to-five-post thread with a 280-character limit per post.
- Draft-only artifacts; no publishing, scheduling, or social APIs.

This completes the core Phase 2 draft-first pipeline.

## Recommended Next Phase 2 Task

Add a controlled `edit-blog` revision loop.

Why this should come next:

- `review-blog` can now correctly stop on `needs_revision`.
- The practical follow-up is helping an owner revise the canonical draft while
  preserving the review's evidence boundaries and then re-running review.
- That creates a complete human-in-the-loop correction loop before introducing
  publishing or automation.

Do not implement it until explicitly requested.

## Runtime Hardening

Status: Complete.

Implemented:

- Atomic `state.json` checkpoints, state validation, and a migration path for
  earlier local run state.
- Strict generated run IDs, run-directory confinement, and clear errors for
  missing or corrupt state.
- A per-run POSIX lock and explicit stage attempt counts for interrupted work.
- Validation that completed, skipped, and blocked stages created their expected
  non-empty artifact inside the run directory.
- Shareable run state/artifacts that use safe labels instead of absolute local
  paths; private resume locations live in ignored owner-only local config.
- Best-effort credential redaction before collected source text reaches a model.
- Public-HTTPS-only resource fetching with private-network and redirect checks.
- Disabled ambient proxy inheritance for resource requests so local proxy
  configuration cannot silently bypass the public-network boundary.
- Bounded model output plus bounded retry behavior for transient API failures.
- Validated positive CLI controls for timeout, retry count, output cap, and
  machine-readable run summaries; limits persist with local resume settings.
- Read-only `validate` command that checks saved state and expected artifacts
  without calling a model or advancing a run.
- Ruff linting, mypy type checks, behavioral tests, and documentation builds in
  the pull-request and `main` quality workflow.

The runtime foundations now support grounded generation, evidence-aware review,
and social transformation without duplicating safety policy in every stage.

## Later Ideas

- Add a simple workflow configuration file.
- Add controlled blog revision and re-review.
- Add a small tool abstraction only when repeated tool behavior appears.

Avoid LangChain, LangGraph, CrewAI, AutoGen, workflow frameworks, vector databases, RAG, embeddings, queues, publishing APIs, and social APIs until there is a clear need.
