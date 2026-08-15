# Architecture Notes

## What Codex Handled In Phase 1

In Phase 1, Codex was the runtime. The Codex Skills described what each capability should do, but Codex handled many invisible responsibilities:

- reading instructions
- deciding which skill applied
- using shell/filesystem tools
- maintaining conversational context
- sequencing stages
- inspecting artifacts before continuing
- stopping when evidence or review quality was insufficient
- writing artifacts to disk
- explaining status to the user

Phase 2 makes those responsibilities explicit in application code.

## Agent vs Runtime

The runtime itself is not the intelligence.

A useful mental model:

```text
Agent = Runtime + Model + Tools + Instructions + State
```

The runtime coordinates execution and persistence. The model provides reasoning and language generation. Tools provide external actions. Instructions define behavior. State records what has happened.

Step 1 implements only the runtime skeleton. The model and real tools come later.

## Runtime Shape

Current Step 1 shape:

```text
CLI
  -> Orchestrator
  -> Run state
  -> Stage executor
  -> Artifacts
```

The orchestrator executes stages in order and persists `state.json` after each transition.

## Orchestration

Some orchestration rules are deterministic:

```text
write-blog must happen before review-blog
```

That does not require model reasoning. It is just workflow order.

Other decisions are agentic:

```text
Do I have enough verified evidence to continue?
```

Step 1 does not implement deep agentic decisions yet, but it creates the runtime places where those decisions will later live: stage results, `blocked` status, and persisted state.

## State

Persistent state matters because multi-step AI workflows are fragile:

- a process can crash
- a tool can fail
- a model can return unusable output
- human review can pause the workflow
- a later stage may need to know exactly what earlier stages produced

Each run stores state at:

```text
runs/<run-id>/state.json
```

The state tracks the subject, run status, current stage, per-stage status, artifact names, messages, and timestamps.

## Resumability

Production workflows cannot assume every multi-step run finishes in one process.

Resume behavior means:

- completed stages do not run again
- skipped stages remain skipped
- failed or blocked runs stay stopped
- interrupted `running` stages can be retried

This lets the runtime recover without losing the audit trail.

## Failed vs Blocked

`failed` means something technically went wrong, such as an exception or invalid stage result.

`blocked` means execution succeeded, but the workflow should not continue safely.

Example future blocked case:

```text
research-work -> insufficient verified evidence -> blocked
```

That distinction is important because blocked runs usually need better inputs or human judgment, not a retry loop.
