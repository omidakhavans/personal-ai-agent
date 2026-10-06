# Personal AI Agent

Phase 2 of the Personal Applied AI Engineering project. Phase 2 is complete;
the repository now also contains the plan for a deliberately incremental
Phase 3 platform evolution.

This repository starts rebuilding the Phase 1 Content Agent outside Codex. Phase 1 lives in `tech-content-agent` and acts as the behavioral reference implementation. This repo implements the first small piece of our own runtime.

## Current Status

Phase 2 now has real, LLM-powered research, evidence-context, blog-writing,
review, LinkedIn, and X stages. Social transformations require a recorded human
approval after the evidence-aware blog review passes.

Phase 3.2 is complete: the runtime now uses typed run and stage snapshots plus
repository and artifact ports, while the original JSON/filesystem implementation
remains the active adapter. It does not yet add PostgreSQL, an API, an operator
UI, background jobs, credentials, or publishing integrations. The next task is
the PostgreSQL persistence adapter. Read the [roadmap](docs/roadmap.md) and
[Phase 3 platform plan](docs/phase-3-platform-plan.md) before starting it.

The runtime lifecycle was validated first with placeholder stages. It now has
eight real stages, including an explicit human approval pause:

- run creation
- run directories
- persistent state
- sequential orchestration
- artifact writing
- failed vs blocked outcomes
- resume behavior
- skipping completed stages during resume
- atomic state checkpoints and a local per-run lock
- verified stage artifacts and recorded execution attempts

`research-work` now gathers a narrow local evidence bundle from a configured
repository, asks a raw OpenAI API call to interpret only that bundle, validates
the structured response, and writes `research-report.md`. It blocks before the
model call when no matching evidence is available.

`research-resources` reads only local paths or URLs explicitly provided with
`--resource`. It writes `resources-report.md`, skips cleanly when no resources
are supplied, and blocks if supplied resources cannot be inspected.

## Safety And Resume Boundaries

Run artifacts and `state.json` use shareable labels such as `local file:
notes.md`; they do not contain absolute local repository or resource paths.
The machine-local locations needed by `resume` are stored separately under the
git-ignored `runs/.runtime-config/` directory with owner-only permissions. Do
not share that directory.

Before source text is sent to the model, the runtime applies a small best-effort
credential redactor. It also limits remote resources to explicitly supplied
public HTTPS URLs, rejects private or reserved network addresses, revalidates
redirects, and limits response size. These guardrails reduce accidental data
exposure; they are not a substitute for reviewing the repositories and sources
you choose to send to a remote model.

State writes are atomic and a per-run lock prevents two local processes from
advancing one run at the same time. Every non-failed stage must leave its
expected non-empty artifact in the run directory before the runtime records it
as successful. Resuming an interrupted stage creates a new recorded attempt,
which can result in another model call and should be intentional.

The runtime also has a read-only `validate` command. It checks that persisted
state is structurally valid and that every stage the state says is available
still has its expected artifact. It makes no model request and does not advance
the workflow.

`build-evidence-context` reads the two research artifacts from the same run,
selects only the strongest traceable claims, and writes `context-brief.md`. It
keeps unknowns, unsupported claims, and missing-resource limitations visible to
the later writing stages.

`write-blog` reads only `context-brief.md`, requires a ready article focus and
traceable evidence references, and writes `blog-draft.md`. Every generated
paragraph and takeaway must cite known work or resource evidence. The artifact
is explicitly `draft_for_human_review`; it is never published by this runtime.

`review-blog` fingerprints the exact saved blog draft, compares it with the
evidence context, and blocks material grounding or technical issues. A passing
review pauses at `approve-social`; only an explicit owner decision allows
`write-linkedin` and `write-x` to produce draft-only social artifacts.

## Workflow

```text
subject
  -> runtime
  -> research-work
  -> research-resources
  -> build-evidence-context
  -> write-blog
  -> review-blog
  -> approve-social
  -> write-linkedin
  -> write-x
```

The stage names mirror the Phase 1 behavior. `research-work` maps back to the Phase 1 `tech-research-work` Codex Skill.

## CLI

Start a new run. Set `OPENAI_API_KEY` in your shell first; it is never saved in
run state or artifacts.

```bash
python -m personal_ai_agent run "What I learned building tool calling" \
  --repository "/path/to/the/project-you-want-to-research" \
  --resource "/path/to/notes/tool-calling.md" \
  --resource "https://platform.openai.com/docs/..."
```

Resume an incomplete run:

```bash
python -m personal_ai_agent resume <run-id>
```

Approve social drafting after reviewing a passing blog review:

```bash
python -m personal_ai_agent approve-social <run-id> \
  --notes "Reviewed the source boundaries."
```

Show persisted state:

```bash
python -m personal_ai_agent show-state <run-id>
```

Validate the state and artifacts without advancing the run:

```bash
python -m personal_ai_agent validate <run-id>
```

Use a custom runs directory:

```bash
python -m personal_ai_agent --runs-dir /tmp/personal-agent-runs run "My subject" \
  --repository "/path/to/project"
```

Pass `--model <name>` to select a model for a new run. The repository and model
are represented with safe labels in run state. Their actual local locations are
kept only in the git-ignored local resume configuration so `resume` can recreate
the stage configuration. Repeat `--resource` to override the saved resource
list during resume. For automation, place `--output-format json` before the
subcommand. `--request-timeout-seconds`, `--max-model-attempts`, and
`--max-output-tokens` make model-call limits explicit; their values are retained
in the local resume configuration. See [the CLI reference](docs/cli-reference.md)
for the full contract.

## Quality Checks

Install the development tools once, then run the same checks used in GitHub
Actions:

```bash
python -m pip install -e ".[dev]"
python -m ruff check personal_ai_agent tests
python -m mypy
python -m unittest discover -s tests
```

`ruff` catches common Python mistakes and import drift, `mypy` checks the typed
interfaces between runtime components, and tests verify runtime behavior. They
do not prove that a model-generated claim is true; evidence validation and human
review remain separate controls. Read [Code Quality](docs/learning/code-quality.md)
for the reasoning behind this boundary.

## Learn The Runtime

Start with [Phase 2 Learning Path](docs/learning/README.md). It links the
end-to-end build guide, runtime walkthrough, and one focused explanation for
each implemented stage.

## Documentation Site

The reviewed learning guides are also available as a static Fumadocs site. Run
`npm ci && npm run dev` to read them locally, or `npm run build` to produce the
GitHub Pages export in `out/`. The Pages workflow is in
`.github/workflows/deploy-docs.yml`; it publishes only after GitHub Pages is
configured to use GitHub Actions.

## Relationship To Phase 1

```text
tech-content-agent
  -> behavioral/reference implementation

personal-ai-agent
  -> runtime implementation
```

Phase 1 proved the content workflow using Codex Skills. Codex handled reasoning, tool execution, filesystem access, state in the conversation, stage judgment, and orchestration.

Phase 2 begins replacing those runtime responsibilities explicitly in our own code.
