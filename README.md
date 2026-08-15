# Personal AI Agent

Phase 2 of the Personal Applied AI Engineering project.

This repository starts rebuilding the Phase 1 Content Agent outside Codex. Phase 1 lives in `tech-content-agent` and acts as the behavioral reference implementation. This repo implements the first small piece of our own runtime.

## Current Status

Step 1 is a minimal local runtime skeleton.

It does not call an LLM yet. Each workflow stage uses a placeholder executor that writes a Markdown artifact, so we can validate runtime lifecycle concerns first:

- run creation
- run directories
- persistent state
- sequential orchestration
- artifact writing
- failed vs blocked outcomes
- resume behavior
- skipping completed stages during resume

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

Start a new run:

```bash
python -m personal_ai_agent run "What I learned building tool calling"
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
python -m personal_ai_agent --runs-dir /tmp/personal-agent-runs run "My subject"
```

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
