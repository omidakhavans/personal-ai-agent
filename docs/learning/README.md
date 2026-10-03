# Phase 2 Learning Path

This folder teaches the Personal AI Agent by following the code that exists in
this repository. Read it in this order.

1. [Phase 2 Agent Build Guide](phase-2-agent-build-guide.md)
   - Start here for the big picture: what an agent runtime is, how a run moves
     through the system, and why the architecture is intentionally small.
2. [Runtime Walkthrough](runtime-walkthrough.md)
   - Follow one CLI command from input through state changes, artifacts, failure,
     blocking, and resume behavior.
3. [Research Work Stage](stage-research-work.md)
   - Learn how the runtime turns a read-only repository into grounded work evidence.
4. [Research Resources Stage](stage-research-resources.md)
   - Learn how explicitly supplied local files and URLs become source-backed knowledge.
5. [Evidence Context Stage](stage-build-evidence-context.md)
   - Learn how the runtime reduces research into a compact writer-ready brief.
6. [Runtime Hardening](runtime-hardening.md)
   - Learn why safety, artifact verification, durable state, and retries belong
     in the runtime rather than in individual AI prompts.

The recommended way to learn is to read one guide, open the named files beside
it, then run the focused tests. Change one small behavior only after you can
predict which state, artifact, and test will change.

## Public Code References

The learning guides may cite public source code directly. Prefer a
repository-relative path, named function or class, and a commit-pinned GitHub
line permalink when explaining a specific implementation. This makes the guide
traceable to the code it teaches. It is safe because this repository is public;
the prohibited material is private machine paths, generated local runs,
credentials, and other local data.

## Current Boundary

The current runtime has three real stages:

```text
research-work -> research-resources -> build-evidence-context
```

The later writing and review stages are intentionally still placeholders. That
lets you learn the research-to-context foundation before adding more generation.

## Run The Tests

From `<project-root>`:

```bash
python -m unittest discover -s tests
```

Tests use fake model clients. They validate the runtime's contracts without
requiring an API key, paid model call, or live website.
