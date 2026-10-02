# Runtime Walkthrough

This document teaches how the Phase 2 runtime currently works. It is not general project documentation. It traces one complete CLI execution from command input to final stage completion, then explains failure, blocking, and resume behavior.

The implementation is intentionally small. The runtime lifecycle was built first;
the `research-work`, `research-resources`, and `build-evidence-context` stages
now make grounded model calls while the remaining stages are placeholders.

## How To Run It

From the repository root:

```bash
cd <project-root>
export OPENAI_API_KEY="..."
python -m personal_ai_agent run "What I learned building tool calling" \
  --repository "/path/to/project-to-research"
```

The command prints:

```text
run_id: <run-id>
status: completed
state artifact: state.json
artifact directory: this run's directory under the configured runs directory
```

Inspect the state:

```bash
python -m personal_ai_agent show-state <run-id>
```

Resume a run:

```bash
python -m personal_ai_agent resume <run-id>
```

Run the tests:

```bash
python -m unittest discover -s tests
```

## The Complete Execution Path

Example command:

```bash
python -m personal_ai_agent run "What I learned building tool calling" \
  --repository "/path/to/project-to-research"
```

### 1. Python Finds The Package Entry Point

File: `personal_ai_agent/__main__.py`

Important function:

- `main()` imported from `personal_ai_agent.cli`

When you run `python -m personal_ai_agent`, Python executes `personal_ai_agent/__main__.py`. That file immediately calls the CLI `main()` function.

Why it exists:

- Ordinary software-engineering reason: it makes the package executable with `python -m ...`.
- Agent-system reason: every workflow needs a clear entry point where outside input enters the runtime.

At this point, there is no agent intelligence yet. This is just normal Python program startup.

### 2. The CLI Parses The Command

File: `personal_ai_agent/cli.py`

Important functions/classes:

- `build_parser()`
- `main(argv=None)`
- `print_run_result(state, runs_dir)`

`build_parser()` defines the commands:

- `run <subject> --repository <path> [--resource <path-or-url>] [--model <name>]`
- `resume <run-id>`
- `show-state <run-id>`

For the example command, `main()` parses:

```text
command = run
subject = What I learned building tool calling
runs_dir = runs
repository = /path/to/project-to-research
model = gpt-4.1-mini
resources = [optional supplied paths or URLs]
```

Then it calls:

```python
Orchestrator(runs_dir=runs_dir, executor=build_content_executor(...)).start(
    args.subject,
    inputs={"repository": "...", "resources": [...], "model": "..."},
)
```

Why it exists:

- Ordinary software-engineering reason: the CLI converts human input into structured arguments.
- Agent-system reason: it defines the first boundary around a run. The subject is the initial task input that later stages will share.

The CLI does not know how research, writing, review, or social generation work. It only starts or resumes the runtime.

### 3. The Orchestrator Creates A New Run

File: `personal_ai_agent/runtime.py`

Important class/function:

- `Orchestrator`
- `Orchestrator.start(subject, inputs=...)`

`start()` does four important things:

1. Creates a unique `run_id` with `new_run_id()`.
2. Computes the run paths with `paths_for_run()`.
3. Creates `runs/<run-id>/`.
4. Builds and writes the initial `state.json`.

Relevant supporting file: `personal_ai_agent/state.py`

Important functions/classes:

- `new_run_id()`
- `paths_for_run(runs_dir, run_id)`
- `RunPaths`
- `initial_state(run_id, subject, inputs)`
- `write_state(state_path, state)`

Why it exists:

- Ordinary software-engineering reason: each execution needs its own directory so outputs do not overwrite each other.
- Agent-system reason: AI workflows often produce multiple intermediate artifacts. A run directory creates an audit trail for what happened and gives later stages stable inputs.

The current run id looks like:

```text
20260815-023441-109e5f0a
```

That combines a timestamp with a short random suffix. The timestamp is useful for humans; the random suffix reduces collisions.

### 4. The Initial State Is Written

File: `personal_ai_agent/state.py`

Important function:

- `initial_state(run_id, subject)`

The initial state has this shape:

```json
{
  "run_id": "...",
  "subject": "What I learned building tool calling",
  "status": "pending",
  "current_stage": "research-work",
  "stages": {
    "research-work": {
      "status": "pending",
      "artifact": "research-report.md"
    }
  }
}
```

The real file includes every stage, messages, timestamps, attempt counts, safe
input labels, and the model name. Absolute repository/resource locations are
kept in an ignored owner-only local resume configuration, not in shareable run
state. The API key stays in the environment; it is never written to disk.

File: `personal_ai_agent/stages.py`

Important constant:

- `WORKFLOW_STAGES`

`WORKFLOW_STAGES` defines the stage order and artifact names:

```text
research-work -> research-report.md
research-resources -> resources-report.md
build-evidence-context -> context-brief.md
write-blog -> blog-draft.md
review-blog -> blog-review.md
write-linkedin -> linkedin-draft.md
write-x -> x-draft.md
```

Why it exists:

- Ordinary software-engineering reason: the state file lets code resume and inspect work without keeping everything in memory.
- Agent-system reason: persistent state is the backbone of reliable multi-step agent workflows. A model call, tool call, or human review step can fail or pause. The workflow needs to remember exactly where it was.

### 5. The Orchestrator Advances The Workflow

File: `personal_ai_agent/runtime.py`

Important function:

- `Orchestrator._advance(state, state_path, run_dir)`

After initialization, `start()` calls `_advance()`.

The first transition is:

```text
run status: pending -> running
```

Then `_advance()` loops through `WORKFLOW_STAGES`.

For each stage, it inspects the stage status:

- `completed`: skip it
- `skipped`: skip it
- `blocked`: stop the run as blocked
- `failed`: stop the run as failed
- `pending`: execute it
- anything else: raise a runtime error

Why it exists:

- Ordinary software-engineering reason: this is the central workflow loop.
- Agent-system reason: orchestration is not just "run the next function." It is where stage gates live. Later, this is where the runtime will stop when evidence is too weak or a review says the draft needs revision.

This is a deterministic workflow rule:

```text
write-blog must run before review-blog
```

That ordering does not require intelligence. It is encoded in `WORKFLOW_STAGES`.

Later, this runtime will also support agentic decisions:

```text
Does research-work have enough verified evidence to continue?
```

That kind of decision depends on content, evidence, and judgment.

### 6. A Stage Moves From Pending To Running

File: `personal_ai_agent/runtime.py`

Important function:

- `Orchestrator._advance(...)`

Before a pending stage executes, `_advance()` updates state:

```text
stage status: pending -> running
current_stage: <stage-name>
started_at: <timestamp>
```

Then it immediately calls `write_state()`.

Why it exists:

- Ordinary software-engineering reason: if the process crashes, the state shows which stage was in progress.
- Agent-system reason: real stages may call models, inspect files, browse docs, or wait on tools. Those operations are not guaranteed to complete. Persisting before execution gives the runtime a recovery point.

### 7. The Placeholder Stage Executor Writes An Artifact

File: `personal_ai_agent/stages.py`

Important classes/functions:

- `Stage`
- `StageResult`
- `StageExecutor`
- `RoutedStageExecutor.execute(stage, subject, run_dir)`
- `ResearchWorkExecutor.execute(stage, subject, run_dir)`

The orchestrator calls:

```python
result = self.executor.execute(
    stage=stage,
    subject=state["subject"],
    run_dir=run_dir,
)
```

For a CLI-created run, `build_content_executor()` in `personal_ai_agent/cli.py`
creates a `RoutedStageExecutor`. It routes `research-work` to
`ResearchWorkExecutor`, `research-resources` to `ResourceResearchExecutor`, and
`build-evidence-context` to `EvidenceContextExecutor`. The rest use
`PlaceholderStageExecutor` for now.

`ResearchWorkExecutor.execute()` has a small grounded sequence:

```text
collect_local_evidence(subject, repository)
  -> no usable evidence: write a report and return blocked
  -> bounded evidence: OpenAIResponsesClient.generate_json(...)
  -> validate_report(...)
  -> render_research_report(...)
  -> return completed
```

The collector uses subject-matched text excerpts and scoped Git metadata. It
does not give the model shell or filesystem access. `OpenAIResponsesClient`
makes one bounded raw HTTP request, and `validate_report()` requires every
`Verified` claim or `Inference` to cite an evidence ID that the collector
actually supplied.

`EvidenceContextExecutor.execute()` does not research again. It reads the
earlier reports in the same run, extracts their `E…` and `R…` IDs, then creates
`context-brief.md`. It rejects claims that cite invented IDs and requires an
interpretation connecting work to resources to cite both kinds of evidence.

Why it exists:

- Ordinary software-engineering reason: the executor separates "how a stage runs" from "how the workflow advances."
- Agent-system reason: each remaining placeholder can be replaced with a real capability that calls a model, uses tools, and decides whether to complete, block, or fail. The orchestrator does not need to know the internals.

This is the first runtime boundary that starts to look agent-shaped: the stage executor is where model intelligence and tool use will eventually live.

### 8. The Orchestrator Persists The Stage Result

File: `personal_ai_agent/runtime.py`

Important function:

- `Orchestrator._advance(...)`

After a stage returns, `_advance()` validates the result status against:

File: `personal_ai_agent/stages.py`

Important constant:

- `TERMINAL_STAGE_STATUSES`

Allowed terminal stage statuses are:

```text
completed
skipped
blocked
failed
```

If the result is valid, the orchestrator records:

```text
stage status
message
finished_at
artifact
```

Then it writes `state.json` again.

Why it exists:

- Ordinary software-engineering reason: results need validation before they become durable state.
- Agent-system reason: when model-powered stages arrive, they may produce malformed or unsafe outputs. The runtime needs explicit contracts and must refuse ambiguous stage outcomes.

### 9. The Runtime Repeats Until The Final Stage

File: `personal_ai_agent/runtime.py`

Important function:

- `Orchestrator._advance(...)`

The same loop repeats for:

```text
research-work
research-resources
build-evidence-context
write-blog
review-blog
write-linkedin
write-x
```

Each stage writes its artifact and updates state.

When all stages are completed or skipped, `_advance()` sets:

```text
run status: completed
current_stage: null
```

Then it writes the final `state.json`.

Why it exists:

- Ordinary software-engineering reason: a workflow needs a final success condition.
- Agent-system reason: downstream processes need to know whether the full chain is usable. A completed run means the grounded research and context stages, plus the remaining placeholder stages, reached terminal success for this version.

In the future, "completed" will not mean "published" or "perfect." It will mean the runtime successfully produced draft artifacts that still need human review.

## Artifact Persistence

Artifacts are Markdown files inside:

```text
runs/<run-id>/
```

Current artifacts:

```text
research-report.md
resources-report.md
context-brief.md
blog-draft.md
blog-review.md
linkedin-draft.md
x-draft.md
```

Responsible code:

- `personal_ai_agent/stages.py`
- `PlaceholderStageExecutor.execute(...)`

Why artifacts exist:

- Ordinary software-engineering reason: files are easy to inspect, diff, test, and pass between stages.
- Agent-system reason: artifacts are the durable context boundary between stages. They prevent the whole workflow from depending on hidden memory inside one long model conversation.

This mirrors Phase 1, where Codex Skills exchanged Markdown artifacts.

## Failure Behavior

Failure means something technically went wrong.

Responsible code:

- `personal_ai_agent/runtime.py`
- `Orchestrator._advance(...)`

There are two failure paths:

1. The executor raises an exception.
2. The executor returns an invalid status.

In both cases, the runtime marks:

```text
stage status: failed
run status: failed
current_stage: <failed-stage>
```

Then it stops.

Why it exists:

- Ordinary software-engineering reason: exceptions and invalid outputs should not be ignored.
- Agent-system reason: model/tool workflows need strong failure boundaries. If research fails, the writer should not quietly invent a blog draft.

Test coverage:

- `tests/test_runtime.py`
- `RuntimeTests.test_failed_stage_stops_workflow`

## Blocking Behavior

Blocked means execution worked, but the workflow should not safely continue.

Responsible code:

- `personal_ai_agent/runtime.py`
- `Orchestrator._advance(...)`
- `personal_ai_agent/stages.py`
- `StageResult(status="blocked", ...)`

Example future blocked condition:

```text
research-work completed its investigation but found insufficient verified evidence
```

The stage should return:

```python
StageResult(
    status="blocked",
    message="Insufficient verified work evidence.",
)
```

The runtime then marks:

```text
stage status: blocked
run status: blocked
current_stage: <blocked-stage>
```

Then it stops.

Why it exists:

- Ordinary software-engineering reason: blocked is a valid business outcome, not a crash.
- Agent-system reason: many useful agent decisions are safety gates. The runtime must be able to say, "I should stop here because continuing would create unsupported content."

Test coverage:

- `tests/test_runtime.py`
- `RuntimeTests.test_blocked_stage_stops_without_marking_failure`

## Resume Behavior

Resume starts from persisted state instead of starting over.

Command:

```bash
python -m personal_ai_agent resume <run-id>
```

Responsible files/classes/functions:

- `personal_ai_agent/cli.py`
- `main(argv=None)`
- `personal_ai_agent/runtime.py`
- `Orchestrator.resume(run_id)`
- `Orchestrator._reset_interrupted_stage(state)`
- `Orchestrator._advance(...)`
- `personal_ai_agent/state.py`
- `read_state(state_path)`
- `write_state(state_path, state)`

`resume()` loads:

```text
runs/<run-id>/state.json
```

If the run is already terminal:

```text
completed
blocked
failed
```

it returns the state and does not continue.

If the run is not terminal, it calls `_reset_interrupted_stage()`. That function changes any stage still marked `running` back to `pending`.

Then `_advance()` runs again.

Completed and skipped stages are not rerun:

```python
if status in {STAGE_COMPLETED, STAGE_SKIPPED}:
    continue
```

Why it exists:

- Ordinary software-engineering reason: long-running jobs need restart behavior.
- Agent-system reason: AI workflows are especially likely to pause or fail mid-run because they depend on tools, model calls, network calls, file access, and human review. Resume lets the runtime preserve previous evidence and continue from the right boundary.

Test coverage:

- `RuntimeTests.test_resume_retries_interrupted_running_stage`
- `RuntimeTests.test_resume_does_not_rerun_completed_stages`

## Component Map

| Component | File | Important class/function | Why it exists |
| --- | --- | --- | --- |
| Package entry point | `personal_ai_agent/__main__.py` | `main()` | Lets `python -m personal_ai_agent` enter the app. |
| CLI parser | `personal_ai_agent/cli.py` | `build_parser()` | Converts command-line text into structured runtime actions. |
| CLI dispatcher | `personal_ai_agent/cli.py` | `main()` | Calls `run`, `resume`, or `show-state`. |
| User result printer | `personal_ai_agent/cli.py` | `print_run_result()` | Shows run id, status, state path, and artifact path. |
| Orchestrator | `personal_ai_agent/runtime.py` | `Orchestrator` | Owns workflow execution and stage gates. |
| New run creation | `personal_ai_agent/runtime.py` | `Orchestrator.start()` | Creates run id, run folder, initial state, then advances. |
| Resume | `personal_ai_agent/runtime.py` | `Orchestrator.resume()` | Loads persisted state and continues safely. |
| Workflow loop | `personal_ai_agent/runtime.py` | `Orchestrator._advance()` | Applies state transitions and executes stages in order. |
| Interrupted stage recovery | `personal_ai_agent/runtime.py` | `_reset_interrupted_stage()` | Lets an interrupted `running` stage be retried. |
| State schema | `personal_ai_agent/state.py` | `initial_state()` | Creates the machine-readable run state. |
| State persistence | `personal_ai_agent/state.py` | `read_state()`, `write_state()` | Reads and writes `state.json`. |
| Run paths | `personal_ai_agent/state.py` | `RunPaths`, `paths_for_run()` | Keeps path construction consistent. |
| Stage contract | `personal_ai_agent/stages.py` | `Stage`, `StageResult`, `StageExecutor` | Defines how stages and executors communicate. |
| Workflow definition | `personal_ai_agent/stages.py` | `WORKFLOW_STAGES` | Defines deterministic stage order and artifact names. |
| Placeholder execution | `personal_ai_agent/stages.py` | `PlaceholderStageExecutor.execute()` | Proves runtime behavior before LLM capability work. |
| Test executor | `personal_ai_agent/stages.py` | `MappingStageExecutor` | Makes failure/blocking/resume scenarios easy to test. |

## Software Engineering vs Agent-System Concepts

Ordinary software-engineering concepts:

- CLI parsing.
- Directory creation.
- JSON serialization.
- Dataclasses.
- Protocols/interfaces.
- Unit tests.
- Exceptions.
- File writes.

Concepts specifically important to AI/agent systems:

- Stage artifacts as durable context boundaries.
- Blocking when evidence is insufficient.
- Separating runtime orchestration from model intelligence.
- Persisting state before and after stage execution.
- Resuming incomplete multi-step workflows.
- Treating review gates as workflow gates.
- Keeping deterministic stage order separate from agentic content decisions.

The overlap matters. A good agent runtime is mostly careful software engineering around unreliable, judgment-heavy steps.

## Documentation Pattern For Future Stages

Each real stage should get similar learning documentation when it replaces a placeholder.

Suggested future docs:

```text
docs/learning/stage-research-work.md
docs/learning/stage-research-resources.md
docs/learning/stage-build-evidence-context.md
docs/learning/stage-write-blog.md
docs/learning/stage-review-blog.md
docs/learning/stage-write-linkedin.md
docs/learning/stage-write-x.md
```

Each stage walkthrough should explain:

- Inputs it receives.
- Artifact it reads.
- Artifact it writes.
- Prompt or deterministic logic it uses.
- Tools it is allowed to use.
- How it decides `completed`, `blocked`, or `failed`.
- What evidence or source references it preserves.
- What hallucination or quality risks it controls.
- How to test it in isolation.

This matters because every stage will eventually combine ordinary code with agent-specific judgment.

## Five Exercises

1. Add a `--runs-dir` example test.
   - Modify `tests/test_runtime.py` to prove a run can be created in a custom runs directory.
   - Run `python -m unittest discover -s tests`.

2. Add a new placeholder stage.
   - Add `review-social` to `WORKFLOW_STAGES` in `personal_ai_agent/stages.py`.
   - Decide its artifact name.
   - Update tests that assume the final artifact is `x-draft.md`.

3. Add a `list-runs` CLI command.
   - Implement it in `personal_ai_agent/cli.py`.
   - It should print run ids and statuses by reading each `state.json`.
   - This proves you understand CLI dispatch and persisted state.

4. Simulate an invalid stage result.
   - Add a test where `MappingStageExecutor` returns `StageResult(status="weird", message="bad")`.
   - Confirm the runtime marks the run as `failed`.
   - This proves you understand stage result validation.

5. Tighten the evidence gate.
   - Modify `collect_local_evidence()` so it also includes a small, allowed set of test files.
   - Add a test proving an unrelated test file is still excluded.
   - Confirm a run with no matching evidence remains `blocked` without a model call.

These exercises are intentionally small. They force you to touch the runtime boundaries where agent systems become real: inputs, state, stage contracts, stopping rules, artifacts, and resume behavior.
