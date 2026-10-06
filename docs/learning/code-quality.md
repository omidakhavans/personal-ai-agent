# Code Quality And Static Analysis

This guide explains how the project checks ordinary runtime code separately from
the quality of AI-generated content. Both matter, but they answer different
questions.

## The Four Checks

From `<project-root>`, install the development tools once:

```bash
python -m pip install -e ".[dev]"
```

Then run:

```bash
python -m ruff check personal_ai_agent tests
python -m mypy
python -m unittest discover -s tests
npm run typecheck
NEXT_PUBLIC_BASE_PATH=/personal-ai-agent npm run build
```

GitHub Actions runs the same Python checks and documentation checks on pull
requests and updates to `main`. The deployment workflow still publishes only
after its documentation build succeeds.

The development-tool versions are pinned in `pyproject.toml`, so the checks run
with the same analyzer behavior locally and in CI until the project deliberately
updates them.

## What Each Tool Proves

`ruff` checks Python syntax-adjacent mistakes, unused imports, fragile patterns,
and import ordering. It is fast feedback while changing implementation code.

`mypy` checks the declared interfaces between components. For this runtime, the
important contracts include `StageExecutor.execute()`, `StageResult`, model
client calls, and the CLI's validated limits. It cannot infer whether JSON from
a model is trustworthy, so the runtime still validates it at the boundary.

The unit tests run the full state machine with fake model clients. They prove
that state transitions, failures, blocking, approval, artifacts, and resume
rules behave as expected without sending data to a provider.

The TypeScript check and static-site build make sure the learning documentation
continues to compile and render as a site.

## What Static Analysis Cannot Prove

No static checker can prove that a model's technical claim is true, that a
selected repository excerpt is representative, or that a human agrees with a
draft. Those are AI-system concerns. This project addresses them through small
evidence bundles, source IDs, schema validation, reviewer findings, and an
explicit human approval checkpoint.

The useful mental model is:

```text
static analysis -> is the program internally consistent?
tests           -> does the program follow its designed behavior?
grounding       -> can a generated claim be traced to supplied evidence?
human review    -> should this draft be trusted and used?
```

None replaces the others.

## Code Documentation Standard

The runtime uses docstrings as its first layer of code documentation:

- every module explains its boundary in one sentence
- every class names the responsibility it owns
- every method explains its contract or state effect
- public helper functions explain the artifact, validation, or model boundary
  they expose

Inline comments are reserved for decisions the code alone cannot make obvious,
such as why a network request must not retry or why a redirect needs a second
validation. Repeating a variable assignment in prose makes code harder to read;
explaining an intentional trade-off makes it easier to maintain.

When you add a stage, start by naming its responsibility in the executor class
docstring. Then document the `execute()` contract: which artifact it writes,
when it blocks, and which boundary it enforces. This turns the source itself
into a dependable learning path without replacing the stage walkthrough.

## Useful Operator Inputs

The CLI validates positive numeric limits before a request starts:

```bash
python -m personal_ai_agent \
  --request-timeout-seconds 45 \
  --max-model-attempts 2 \
  --max-output-tokens 1800 \
  --output-format json \
  run "A grounded topic" --repository "/path/to/project"
```

These are operational controls, not prompt instructions. They keep expected
latency, retries, and response size visible in the command that starts a run.
The runtime preserves them in local resume configuration so a resumed run does
not silently change its limits.

## Exercises

1. Deliberately add an unused import, run `ruff`, then remove it.
2. Change a `StageResult` status to an invalid value and observe the type-check
   and runtime validation boundaries.
3. Add a test for a malformed timestamp in `state.json`.
4. Add one validated CLI argument with a clear operational purpose and document
   whether it must persist for resume.
5. Change a model-output schema, then update the validator and the fake-model
   test together. Explain why the type checker alone did not catch the change.
