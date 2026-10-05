# Personal AI Agent

Phase 2 of the Personal Applied AI Engineering project.

This repository starts rebuilding the Phase 1 Content Agent outside Codex. Phase 1 lives in `tech-content-agent` and acts as the behavioral reference implementation. This repo implements the first small piece of our own runtime.

## Current Status

Phase 2 now has real, LLM-powered `research-work`, `research-resources`,
`build-evidence-context`, and `write-blog` stages. Review and social stages are
still placeholders.

The runtime lifecycle was validated first with placeholder stages. It now has
four real stages while the remaining stages still use placeholders:

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

`build-evidence-context` reads the two research artifacts from the same run,
selects only the strongest traceable claims, and writes `context-brief.md`. It
keeps unknowns, unsupported claims, and missing-resource limitations visible to
the later writing stages.

`write-blog` reads only `context-brief.md`, requires a ready article focus and
traceable evidence references, and writes `blog-draft.md`. Every generated
paragraph and takeaway must cite known work or resource evidence. The artifact
is explicitly `draft_for_human_review`; it is never published by this runtime.

## Workflow

```text
subject
  -> runtime
  -> research-work
  -> research-resources
  -> build-evidence-context
  -> write-blog
  -> review-blog
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

Show persisted state:

```bash
python -m personal_ai_agent show-state <run-id>
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
list during resume.

## Tests

Run tests with the standard library:

```bash
python -m unittest discover -s tests
```

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
