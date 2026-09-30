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

## Recommended Next Phase 2 Task

Add a real `research-resources` capability.

Why this should come next:

- `research-work` can now produce a grounded local evidence report.
- External or user-supplied references are the next missing input to the evidence-context stage.
- It extends the same pattern: controlled inputs, source references, structured model output, and explicit uncertainty.

Suggested scope:

```text
research-resources executor
  -> accept explicit URLs and local reference paths
  -> collect bounded resource text and source metadata
  -> call a raw LLM API with bounded context
  -> write resources-report.md
  -> return completed, skipped, or blocked
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
