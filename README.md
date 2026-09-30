# Personal AI Agent

Phase 2 of the Personal Applied AI Engineering project.

This repository starts rebuilding the Phase 1 Content Agent outside Codex. Phase 1 lives in `tech-content-agent` and acts as the behavioral reference implementation. This repo implements the first small piece of our own runtime.

## Current Status

Step 2 begins with a real, LLM-powered `research-work` stage. The remaining
stages are still placeholders.

The runtime lifecycle was validated first with placeholder stages. It now has one
real stage while the remaining stages still use placeholders:

- run creation
- run directories
- persistent state
- sequential orchestration
- artifact writing
- failed vs blocked outcomes
- resume behavior
- skipping completed stages during resume

`research-work` now gathers a narrow local evidence bundle from a configured
repository, asks a raw OpenAI API call to interpret only that bundle, validates
the structured response, and writes `research-report.md`. It blocks before the
model call when no matching evidence is available.

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
  --repository "/path/to/the/project-you-want-to-research"
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
are persisted as non-secret run inputs so `resume` can recreate the stage
configuration.

## Tests

Run tests with the standard library:

```bash
python -m unittest discover -s tests
```

## Relationship To Phase 1

```text
tech-content-agent
  -> behavioral/reference implementation

personal-ai-agent
  -> runtime implementation
```

Phase 1 proved the content workflow using Codex Skills. Codex handled reasoning, tool execution, filesystem access, state in the conversation, stage judgment, and orchestration.

Phase 2 begins replacing those runtime responsibilities explicitly in our own code.
