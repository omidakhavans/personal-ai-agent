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

- CLI entrypoint with `run`, `resume`, and `show-state`.
- Unique run ids.
- Run directories under `runs/<run-id>/`.
- Machine-readable `state.json`.
- Sequential stage orchestration.
- Placeholder stage executor.
- Markdown artifacts for each stage.
- State persistence after every transition.
- Distinction between `failed` and `blocked`.
- Resume behavior that avoids rerunning completed stages.
- Tests for creation, state initialization, stage progression, artifacts, persistence, failed behavior, blocked behavior, resume behavior, and completed-stage reuse.

Current placeholder workflow:

```text
subject
  -> research-work
  -> research-resources
  -> build-evidence-context
  -> write-blog
  -> review-blog
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

## Recommended Next Phase 2 Task

Add a real `write-blog` capability.

Why this should come next:

- `research-work` and `research-resources` now produce traceable source reports.
- `build-evidence-context` now reduces them to one high-signal, grounded brief.
- A blog draft is the next canonical artifact from which later social content can derive.

Suggested scope:

```text
write-blog executor
  -> read context-brief.md
  -> generate a technical article draft from selected evidence only
  -> preserve source references and open uncertainties for human review
  -> call a raw LLM API with bounded context
  -> write blog-draft.md
  -> return completed or blocked
```

Do not implement this until explicitly requested.

## Later Ideas

- Add a simple workflow configuration file.
- Add real resource research.
- Add context-building logic.
- Add grounded blog generation.
- Add evidence-aware review.
- Add social transformation.
- Add human approval checkpoints.
- Add a small tool abstraction only when repeated tool behavior appears.

Avoid LangChain, LangGraph, CrewAI, AutoGen, workflow frameworks, vector databases, RAG, embeddings, queues, publishing APIs, and social APIs until there is a clear need.
