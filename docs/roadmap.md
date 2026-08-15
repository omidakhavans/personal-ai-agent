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

## Recommended Next Phase 2 Task

Add the first raw LLM-powered capability for `research-work`.

Why this should come next:

- The runtime lifecycle now exists and can execute, persist, block, fail, and resume.
- `research-work` is the first stage in the workflow, so replacing its placeholder with a real capability gives the rest of the pipeline meaningful input.
- It is the best place to learn the next layer of agent internals: model calls, prompt construction, local tool access, evidence extraction, and explicit blocked decisions when evidence is insufficient.

Suggested scope:

```text
research-work executor
  -> inspect a configured local repository
  -> collect narrow file/git evidence
  -> call a raw LLM API with bounded context
  -> write research-report.md
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
