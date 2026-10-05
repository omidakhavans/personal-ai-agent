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

Phase 2 now has the complete draft-first workflow: grounded repository and
resource research, evidence-context construction, blog drafting, evaluation,
human approval, and platform-specific social transformation.

## Runtime Shape

Current runtime shape:

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
review-blog must pass before human approval
human approval must happen before social transformation
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

For real stages, state records safe, shareable input labels and the selected
model. Local repository/resource locations needed for resume live in a separate,
git-ignored owner-only configuration file. API keys never enter either file.

The runtime writes state through a temporary file and an atomic replacement, and
uses one POSIX file lock per run. This is ordinary durability and concurrency
engineering, but it matters especially for agent workflows because a model call
may be slow, paid, and non-deterministic. Each stage records its attempt count;
an interrupted `running` stage runs again only after an explicit `resume`.

## Grounded Research

The `research-work` stage is intentionally split into two responsibilities:

```text
local evidence collector -> bounded evidence bundle -> model interpretation -> validated report
```

The collector reads a small, subject-matched set of repository files and scoped
Git metadata. The model receives that selected bundle, not unrestricted filesystem
access. The runtime validates that every `Verified` model claim cites a supplied
evidence identifier before it persists the Markdown report.

Before source text crosses the model boundary, the collector applies a small
best-effort credential redactor. Artifact references use repository-relative
paths or safe local labels, never absolute user-machine paths. Source selection
still requires human judgment: automated redaction reduces common mistakes but
cannot prove that a chosen source has no sensitive information.

This does not prove every claim is true: the model can still misinterpret an
excerpt. It does make the claim inspectable and prevents the model from citing
invented source identifiers.

## Supplied Resource Research

`research-resources` follows the same boundary for external knowledge:

```text
explicit local path or URL -> bounded resource text -> model interpretation -> validated report
```

V1 does not discover web sources by itself. It reads only `--resource` values
the user supplied. No supplied resources produces a `skipped` report, while
supplied resources that all fail to load produce `blocked`. This keeps a missing
optional enrichment step distinct from a failure to honor an explicit source.

Remote resources are limited to public HTTPS URLs. The collector rejects private,
loopback, link-local, and reserved addresses before a request and again on each
redirect. This is a network safety boundary: without it, a user-supplied URL
could cause the local runtime to fetch an internal service and forward its text
to a remote model.

The report uses resource IDs such as `R1`. Source facts and interpretations must
cite those IDs; the runtime rejects invented resource references before writing
`resources-report.md`.

## Grounded Blog Drafting

`write-blog` receives one prepared `context-brief.md`, not the repository or
raw resources:

```text
context brief -> cited structured draft -> validated blog-draft.md
```

The writer requires a ready article focus and at least one traceable source ID.
Each generated paragraph and takeaway carries known `E...` or `R...` IDs, which
the runtime validates before rendering Markdown. This constrains generation to
prepared evidence while leaving the model room to choose useful structure and
language. It does not replace human editorial or technical review.

## Evaluation And Approval

`review-blog` compares `blog-draft.md` with `context-brief.md` and writes a
fingerprinted `blog-review.md`. Findings quote the saved article and cite known
evidence IDs when support exists. Material grounding or technical findings block
the run with `needs_revision`; a passing review remains only
`ready_for_human_review`.

The next stage is deliberately not another model call. `approve-social` writes
an approval request and puts the run in `awaiting_approval`. The owner must run
the explicit approval command before downstream draft generation. This makes a
human judgment a visible state transition rather than an assumption hidden in a
prompt.

## Controlled Social Transformation

The LinkedIn and X writers receive the reviewed blog, its matching review, and
the approval record. They do not receive repository access or raw research.
Both return structured, evidence-cited output; X additionally validates its
single-post or thread shape and 280-character maximum per post. Neither stage
publishes or calls a social API.

## Evidence Context

`build-evidence-context` is the boundary between research and generation:

```text
research-report.md + resources-report.md
  -> selected claim packet
  -> model synthesis with reference IDs
  -> validated context-brief.md
```

It does not rerun repository or resource research. It reads the artifacts already
produced by those stages, keeps their `E…` and `R…` references, and asks the
model to reduce rather than expand the material. A context claim about the user's
work must cite work evidence; a work-resource connection must cite both types.

This is context engineering in practice: a later writer receives fewer, clearer,
grounded claims instead of two raw reports and an invitation to reconstruct the
story. If work research is missing, the stage blocks. Missing optional resource
research produces a work-only brief with that limitation recorded.

## Resumability

Production workflows cannot assume every multi-step run finishes in one process.

Resume behavior means:

- completed stages do not run again
- skipped stages remain skipped
- failed or blocked runs stay stopped
- approval-paused runs wait for an explicit owner decision
- interrupted `running` stages can be retried

The runtime also verifies previously completed artifacts before resuming. A
state file alone is not enough evidence that an earlier stage actually produced
the file a later stage needs.

This lets the runtime recover without losing the audit trail.

## Failed vs Blocked

`failed` means something technically went wrong, such as an exception or invalid stage result.

`blocked` means execution succeeded, but the workflow should not continue safely.

Example future blocked case:

```text
research-work -> insufficient verified evidence -> blocked
```

That distinction is important because blocked runs usually need better inputs or human judgment, not a retry loop.
