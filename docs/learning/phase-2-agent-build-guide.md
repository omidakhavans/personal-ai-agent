# Building The Phase 2 Personal AI Agent

This guide explains the agent runtime we are building in `personal-ai-agent`.
It is deliberately about the implementation in this repository, not an abstract
definition of agents.

The current objective is modest and useful: rebuild the first part of the Phase
1 Content Agent outside Codex, using ordinary Python code plus raw model calls.
The system should be inspectable, resumable, evidence-grounded, and safe to stop
when it does not know enough.

## 1. Start With The Right Mental Model

An agent is not just a model call.

```text
Agent = Runtime + Model + Tools + Instructions + State
```

In this project:

| Part | Current implementation | Why it matters |
| --- | --- | --- |
| Runtime | `personal_ai_agent/runtime.py` | Runs stages in order, persists status, and stops safely. |
| Model | `personal_ai_agent/model_client.py` | Turns bounded evidence into structured reasoning. |
| Tools | Local file/Git reads and explicit URL reads | Gather evidence without giving the model unlimited access. |
| Instructions | Each stage's prompt function | Defines the task, boundaries, and output contract. |
| State | `runs/<run-id>/state.json` | Lets the workflow recover, inspect progress, and resume. |
| Artifacts | Markdown files in the run directory | Give later stages visible, durable inputs. |

Most of this is ordinary software engineering. The agent-specific part is how we
handle uncertain model output: bounded input, structured output, evidence IDs,
validation, and a `blocked` outcome when continuing would be misleading.

## 2. What Exists Today

The workflow has seven named stages, but only the first four are real:

```text
subject
  -> research-work                 real
  -> research-resources            real
  -> build-evidence-context        real
  -> write-blog                    real
  -> review-blog                   placeholder
  -> write-linkedin                placeholder
  -> write-x                       placeholder
```

The full stage order lives in `personal_ai_agent/stages.py` as
`WORKFLOW_STAGES`. Keeping it explicit makes one rule deterministic:

```text
research happens before writing
writing happens before review
```

The runtime does not ask a model to choose the order. That would add
unpredictability to something normal application code can guarantee.

## 3. Trace One Run

Start a run from `<project-root>`:

```bash
export OPENAI_API_KEY="..."
python -m personal_ai_agent run "What I learned building tool calling" \
  --repository "/path/to/project" \
  --resource "/path/to/notes.md"
```

The command flows through these components:

```text
__main__.py
  -> cli.main()
  -> cli.build_content_executor()
  -> Orchestrator.start()
  -> state.initial_state()
  -> Orchestrator._advance()
  -> RoutedStageExecutor.execute()
  -> one stage executor
  -> Markdown artifact + updated state.json
```

Open [Runtime Walkthrough](runtime-walkthrough.md) beside the code for the full
line-by-line explanation. The important idea is that the runtime records a
checkpoint before and after each stage. A model, network request, or process can
fail halfway through; `state.json` answers, “what completed, what stopped, and
what artifact already exists?”

## 4. The Run Directory Is The Agent's Working Memory

Each run gets its own directory:

```text
runs/<run-id>/
  state.json
  research-report.md
  resources-report.md
  context-brief.md
  blog-draft.md
  blog-review.md
  linkedin-draft.md
  x-draft.md
```

This is not a database yet. It is intentional prototype storage: visible,
diffable, simple to test, and easy to resume. The state file tracks status; the
Markdown artifacts carry the actual content between stages.

Do not confuse `completed` with “true” or “published.” It means the stage met
its runtime contract and wrote its artifact. Human review remains necessary.

## 5. Stage One: Work Research

`ResearchWorkExecutor` in `personal_ai_agent/research_work.py` is the first
grounding boundary.

```text
subject + read-only repository
  -> selected local evidence
  -> bounded model input
  -> structured research report
```

The application, not the model, chooses the repository files and scoped Git
metadata to inspect. The model gets excerpts, not a shell or unrestricted file
access. Claims marked `Verified` or `Inference` must cite an evidence ID such
as `E1`.

Read [Research Work Stage](stage-research-work.md) next for the collector,
prompt, validation, and blocked behavior.

## 6. Stage Two: Resource Research

`ResourceResearchExecutor` in `personal_ai_agent/research_resources.py` handles
the knowledge sources you explicitly provide:

```text
--resource local path or URL
  -> bounded readable text
  -> structured resource report
```

This stage does not do independent web discovery. That is a deliberate product
choice: the user chooses the sources, then the agent extracts useful knowledge
with traceable IDs such as `R1`.

No resources means `skipped`, which is safe because a work-only article may
still be possible. Resources were supplied but none could be read means
`blocked`, because replacing requested sources with guesses would be dishonest.

Read [Research Resources Stage](stage-research-resources.md) for the exact
handling rules.

## 7. Stage Three: Context Engineering

`EvidenceContextExecutor` in `personal_ai_agent/evidence_context.py` is the
bridge from research to writing.

```text
research-report.md + resources-report.md
  -> select useful facts
  -> keep uncertainty visible
  -> preserve E and R references
  -> context-brief.md
```

Why not give the blog writer both raw reports? Because large context is not the
same as good context. Raw research includes repeated details, tangents, weak
claims, and unclear connections. A writer with all of it has more ways to
accidentally produce a persuasive but unsupported story.

The context stage performs a deliberate reduction. It selects high-signal facts,
separates verified work from external knowledge, labels interpretation, records
claims that must not be stated as fact, and recommends one article focus.

Read [Evidence Context Stage](stage-build-evidence-context.md) for the source-ID
rules and its safety gates.

## 8. Structured Output Is A Runtime Contract

Each real stage asks the model for JSON, not free-form Markdown. The runtime then
validates it before rendering Markdown itself.

For example, a context claim looks like:

```json
{
  "label": "Interpretation",
  "claim": "A connection supported by the supplied evidence.",
  "work_evidence_ids": ["E1"],
  "resource_ids": ["R1"]
}
```

`validate_context_brief()` enforces the rules:

- a verified work claim needs at least one `E…` ID;
- verified external knowledge needs at least one `R…` ID;
- a connection between work and resources needs both; and
- unknown IDs cause the stage to fail rather than become part of the artifact.

This is not a guarantee that the model understood every source correctly. It is
a practical reliability layer: you can inspect how a claim entered the system,
and the model cannot cite made-up sources.

## 9. Completed, Skipped, Blocked, And Failed

These status values are central to the runtime.

| Status | Meaning | Example |
| --- | --- | --- |
| `completed` | The stage fulfilled its contract. | Context brief was validated and saved. |
| `skipped` | The stage was optional and had no input. | No resources were supplied. |
| `blocked` | Continuing would be unsafe or unsupported. | No repository evidence exists for the subject. |
| `failed` | A technical or contract error occurred. | A model returned invalid JSON or cited an unknown ID. |

`blocked` is an agent behavior, not an exception. It means “stop and ask for
better evidence or human judgment.” `failed` means “the system needs a technical
fix, retry, or configuration change.”

## 10. How We Test Agent Behavior

The tests live in `tests/test_runtime.py`. They use `FakeModelClient` rather
than a live model. This is important.

We can test deterministic contracts without paying for model calls:

- a run creates state and artifacts;
- completed stages are not rerun on resume;
- no work evidence blocks before calling the model;
- no resources produces a skipped report;
- inaccessible resources block;
- context preserves valid references; and
- invented evidence IDs are rejected.

Live model evaluation is still valuable, but it is a different activity. Unit
tests prove runtime rules; sample runs with real artifacts help judge research
quality, writing usefulness, and prompt behavior.

## 11. Stage Four: Grounded Blog Writing

`write-blog` reads only `context-brief.md`. It does not restart research or
browse the repository.

Its job will be grounded generation:

```text
context-brief.md
  -> article structure and draft
  -> blog-draft.md
  -> human review
```

The writer returns structured JSON with cited paragraphs and takeaways. The
runtime rejects unknown or empty citations, then renders `blog-draft.md` with
source references and review caveats. The writer may choose language and
structure, but it should not invent what you built. After that, `review-blog`
becomes the next quality gate before LinkedIn and X transformations.

## 12. Exercises

1. Add one sentence to `context_instructions()` explaining what the model should
   do when work and resource evidence disagree. Add a test for your chosen rule.
2. Add a small `Author Context` input to the CLI, persist it in state, and make
   `EvidenceContextExecutor` include it in `context-brief.md` without treating
   it as factual evidence.
3. Add a test that proves `EvidenceContextExecutor` blocks when a context brief
   returns `recommended_article_focus.status = "insufficient_evidence"`.
4. Add a maximum total context-size limit across both research reports and make
   the failure message explain which artifact is too large.
5. Implement `review-blog` using the same pattern: bounded artifact input,
   structured model output, validation, Markdown rendering, tests, and a stage
   walkthrough.

These exercises are useful because they force you to work at the places where
agent systems become dependable: inputs, state, evidence, decision gates,
artifacts, and evaluation.
