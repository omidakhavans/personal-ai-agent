# Personal AI Agent Learning Path

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
6. [Write Blog Stage](stage-write-blog.md)
   - Learn how structured, cited generation turns the brief into a draft for review.
7. [Review Blog Stage](stage-review-blog.md)
   - Learn how an evaluator checks the draft against its evidence before it can travel further.
8. [Social Approval Stage](stage-approve-social.md)
   - Learn how a human decision becomes durable workflow state.
9. [Write LinkedIn Stage](stage-write-linkedin.md)
   - Learn how a reviewed article is adapted without recreating the story.
10. [Write X Stage](stage-write-x.md)
   - Learn how concise, controlled generation chooses a post or thread.
11. [Runtime Hardening](runtime-hardening.md)
   - Learn why safety, artifact verification, durable state, and retries belong
     in the runtime rather than in individual AI prompts.
12. [Code Quality And Static Analysis](code-quality.md)
   - Learn what linting, type checking, tests, grounding, and human review each
     prove, and where their guarantees stop.
13. [Phase 3 Platform Planning](phase-3-platform-planning.md)
   - Learn how the working local runtime can grow into a production-style agent
     platform without losing its evidence and approval boundaries.

The recommended way to learn is to read one guide, open the named files beside
it, then run the focused tests. Change one small behavior only after you can
predict which state, artifact, and test will change. Phase 3 is currently a
plan: read its guide before implementing the first persistence-boundary task.

## Public Code References

The learning guides may cite public source code directly. Prefer a
repository-relative path, named function or class, and a commit-pinned GitHub
line permalink when explaining a specific implementation. This makes the guide
traceable to the code it teaches. A code reference does not expose the private
runtime data that must stay out of documentation: machine paths, generated local
runs, credentials, and other local data.

## Current Boundary

The current runtime has eight real stages:

```text
research-work -> research-resources -> build-evidence-context -> write-blog
  -> review-blog -> approve-social -> write-linkedin -> write-x
```

The run pauses at `approve-social` after a passing review. The owner must run
the explicit approval command before the two social drafts are generated.

## Run The Tests

From `<project-root>`:

```bash
python -m unittest discover -s tests
```

Tests use fake model clients. They validate the runtime's contracts without
requiring an API key, paid model call, or live website.
