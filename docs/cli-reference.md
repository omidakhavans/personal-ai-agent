# CLI Reference

The command-line interface is the operator boundary for the local runtime. It
creates, resumes, approves, inspects, and validates runs; it never publishes
content.

Run `python -m personal_ai_agent --help` for the current command help.

## Global Options

Place global options before the command.

| Option | Purpose |
| --- | --- |
| `--runs-dir <path>` | Stores run directories and machine-local resume configuration. Defaults to `./runs`. |
| `--output-format text\|json` | Formats run and validation summaries for a person or another program. `show-state` always prints the complete saved state JSON. |
| `--request-timeout-seconds <positive-int>` | Caps one model API request. The default is 60 seconds. |
| `--max-model-attempts <positive-int>` | Caps attempts for retryable model API responses. The default is 3. Connection failures are not retried automatically. |
| `--max-output-tokens <positive-int>` | Overrides the output limit for every model-backed stage in the run. Leave it unset to use each stage's conservative default. |

The model limits are saved only in the ignored local resume configuration. They
are not credentials, but keeping them with the original run means a later
`resume` keeps the same operational limits unless you explicitly override them.

## Commands

### Start a run

```bash
python -m personal_ai_agent run "What I learned building tool calling" \
  --repository "/path/to/project" \
  --resource "/path/to/note.md" \
  --resource "https://example.com/reference"
```

`run` requires:

- a non-empty subject
- `--repository`, a local directory read by `research-work`
- `OPENAI_API_KEY` in the shell environment for real model-backed stages

Repeat `--resource` to supply local UTF-8 text files or public HTTPS resources.
The runtime does not discover sources on its own.

Use `--model <name>` to select a model. The default remains the project's
default model. The model is a runtime input, not evidence for a content claim.

### Resume a run

```bash
python -m personal_ai_agent resume <run-id>
```

`resume` uses the local configuration saved when the run began. You may provide
`--repository`, `--model`, or one or more `--resource` options again to replace
the saved values. Completed stages are not rerun. A `blocked`, `failed`, or
approval-paused run remains stopped so its reason stays visible.

### Inspect state

```bash
python -m personal_ai_agent show-state <run-id>
```

This command prints the full persisted `state.json` for local diagnosis. Do not
paste an entire state file into a public issue without reviewing its subject and
safe input labels first.

### Validate saved work

```bash
python -m personal_ai_agent --output-format json validate <run-id>
```

`validate` is read-only. It validates state shape, stage names, expected artifact
names, and every non-failed artifact the run claims is available. It does not
call a model, change state, or rerun a stage. This is useful before handoff,
archive, or a manual investigation of a stopped run.

### Approve social transformations

```bash
python -m personal_ai_agent approve-social <run-id> \
  --notes "I checked the evidence boundaries."
```

This succeeds only when the blog review is ready and the workflow is explicitly
awaiting approval. It fingerprints the reviewed blog before generating
LinkedIn and X drafts. It still does not publish them.

## Exit Behavior

Invalid arguments and unavailable run state produce a non-zero command result
with a clear message. A workflow that becomes `blocked`, `failed`, or
`awaiting_approval` is a valid runtime outcome: inspect its artifact and decide
what must change before starting a new or revised run.
