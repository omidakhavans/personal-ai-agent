# Stage Walkthrough: `research-work`

`research-work` is the first real capability in the Phase 2 runtime. It turns a
subject and a read-only repository path into a traceable `research-report.md`.
It does not write the blog article and it does not give the model unrestricted
access to the repository.

## Run It

From the repository root, provide an API key only through the environment:

```bash
export OPENAI_API_KEY="..."
python -m personal_ai_agent run "What I learned building tool calling" \
  --repository "/path/to/project-to-research"
```

The report is saved at:

```text
runs/<run-id>/research-report.md
```

Use `--model <name>` on a new run to choose the model. `state.json` stores a
safe repository label and model name; the actual local repository location used
by `resume <run-id>` is stored separately in ignored owner-only local config.
The API key is never saved.

## Execution Path

The CLI function `build_content_executor()` in `personal_ai_agent/cli.py`
creates three objects:

```text
ResearchWorkSettings
  -> ResearchWorkExecutor
  -> RoutedStageExecutor
```

`RoutedStageExecutor.execute()` in `personal_ai_agent/stages.py` directs the
`research-work` stage to `ResearchWorkExecutor.execute()` in
`personal_ai_agent/research_work.py`. The same routing boundary now directs
every later capability to its own executor.

`ResearchWorkExecutor.execute()` performs this sequence:

```text
subject + repository
  -> collect_local_evidence()
  -> no evidence: report + blocked
  -> bounded evidence bundle
  -> OpenAIResponsesClient.generate_json()
  -> validate_report()
  -> render_research_report()
  -> research-report.md + completed
```

## Inputs

- Subject: the CLI positional argument.
- Repository: required with `run --repository`; treated as read-only.
- Model: `--model`, defaulting to `gpt-4.1-mini`.
- API key: `OPENAI_API_KEY` in the process environment.

`ResearchWorkSettings` holds the repository and model. `OpenAIResponsesClient`
reads the API key only when it needs to make the request. This keeps credentials
out of CLI arguments, run state, reports, and Git.

## Evidence Collection

`collect_local_evidence(subject, repository)` creates an `EvidenceBundle`.

`subject_terms()` extracts a small search vocabulary from the subject. The
collector first considers high-signal documentation files, then uses `rg` to
find text files matching those terms. It reads excerpts around matching lines,
not full unrelated files. It ignores individual files larger than 512 KB and
limits the evidence set to 12 matched files.

When Git data is available, `_git_output()` adds scoped branch, status, history,
and working-tree diff metadata for those same matched files. Every selected item
receives an identifier such as `E1` or `E2`.

Why this exists:

- Software engineering: bounded inputs make work predictable, debuggable, and inexpensive.
- Agent systems: a model is more reliable when it reasons over selected evidence rather than an unbounded repository or an assumed memory of the project.

The model never runs shell commands, reads files, or decides which extra paths
to inspect. Those are application-controlled actions.

Before excerpts or Git metadata enter the model prompt, common credential-shaped
values are redacted as a best-effort safeguard. The report uses repository-
relative references and a safe repository label rather than an absolute path.

## Model Boundary

`OpenAIResponsesClient.generate_json()` sends one raw HTTP request to the
Responses API. There is no SDK or orchestration framework in the runtime.

The prompt provides the subject, repository metadata, and evidence excerpts. It
asks for a fixed JSON structure containing traceable summaries, claims, decisions,
problems, approaches, technologies, lessons, and unknowns. Claim objects carry:

```json
{
  "status": "Verified",
  "claim": "A supported statement about the work.",
  "evidence_ids": ["E1"]
}
```

The model has room to make an interpretation, but it has no authority to turn
that interpretation into untraceable fact. Repository excerpts are explicitly
treated as data, not instructions for the model to follow.

## Validation And Artifact

`validate_report()` rejects a response when it:

- is not the required JSON shape;
- has an invalid claim status;
- cites an evidence ID not in the local bundle; or
- labels a `Verified` claim or `Inference` without citing evidence.

If validation succeeds, `render_research_report()` creates a Markdown report in
the Phase 1-compatible shape: subject, scope, implementation, decisions,
problems, approaches, technologies, lessons, unknowns, and evidence references.

Validation cannot prove that the model interpreted an excerpt correctly. It
does make each verified claim inspectable and rejects fabricated citations. A
human still reviews the report before using it as a public claim.

## Completion, Blocking, And Failure

- `completed`: local evidence was collected, the model response passed
  validation, and `research-report.md` was saved.
- `blocked`: no subject-matched evidence was found. The stage writes a short
  report explaining that it cannot safely continue, and later stages do not run.
- `failed`: a repository path is invalid, the API request fails, the model
  returns invalid JSON, or validation rejects the response. The runtime records
  the error in `state.json`.

This distinction is important. A blocked run usually needs a better subject or
repository scope; a failed run may need a technical retry or correction.

## Test It In Isolation

`tests/test_runtime.py` includes three focused checks:

- `test_collects_narrow_subject_evidence`
- `test_real_research_stage_writes_grounded_report_then_pipeline_continues`
- `test_insufficient_evidence_blocks_without_calling_model`

The tests use `FakeModelClient`, not an API key or live model. That keeps the
runtime contract testable and proves the grounding and stop rules separately
from provider availability.
