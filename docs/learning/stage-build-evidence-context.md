# Stage Walkthrough: `build-evidence-context`

`build-evidence-context` is the bridge between research and writing. It reads
the research artifacts already created in one run and produces a smaller,
traceable `context-brief.md` for the future blog writer.

It does not inspect the repository, fetch more URLs, or write the article.

## Where It Fits

```text
research-work -> research-report.md
research-resources -> resources-report.md
build-evidence-context -> context-brief.md
write-blog -> blog-draft.md
```

The research stages maximize reliable collection. This stage optimizes what the
next model should see. Those are different jobs.

## Execution Path

`build_content_executor()` in `personal_ai_agent/cli.py` creates an
`EvidenceContextExecutor` with `EvidenceContextSettings`. `RoutedStageExecutor`
in `personal_ai_agent/stages.py` sends the `build-evidence-context` stage to it.

`EvidenceContextExecutor.execute()` in `personal_ai_agent/evidence_context.py`
does this:

```text
research-report.md + resources-report.md
  -> collect_context_inputs()
  -> extract E… and R… source IDs
  -> bounded model input
  -> OpenAIResponsesClient.generate_json()
  -> validate_context_brief()
  -> context-brief.md
```

## Inputs

The stage has no new CLI flags. It receives its inputs from the current run
directory:

- `research-report.md` is required. It describes the user's actual work.
- `resources-report.md` is optional. It adds supplied external or local context.
- The subject is passed from the run state.
- The selected model and `OPENAI_API_KEY` use the same shared client as the
  research stages.

The context stage reads at most 40 KB from each research artifact. This keeps
the model input bounded and makes a bloated or accidental artifact visible as a
clear error instead of silently expanding the prompt.

## Reference Preservation

The stage extracts evidence IDs from source-report reference sections:

- `E1`, `E2`, and similar IDs represent work evidence.
- `R1`, `R2`, and similar IDs represent resources.

The model must return each selected item with a label and the IDs supporting it:

```json
{
  "label": "Interpretation",
  "claim": "A connection supported by both kinds of evidence.",
  "work_evidence_ids": ["E1"],
  "resource_ids": ["R1"]
}
```

`validate_context_brief()` rejects unknown IDs. A `Verified work evidence` claim
needs work evidence, a `Verified external knowledge` claim needs a resource, and
a work-resource connection needs both. This protects a later writer from being
given plausible but untraceable synthesis.

## Context Engineering

Giving a writer every raw report is tempting, but more context is not always
better. It makes the next model spend attention on duplicates, implementation
trivia, and weak claims. It can also blur the difference between a fact and an
interpretation.

The context brief deliberately selects:

- the strongest work facts;
- relevant external concepts;
- evidence-supported connections;
- useful technical lessons and content angles;
- claims that must not be stated as fact; and
- unresolved conflicts or limitations.

It deliberately excludes irrelevant material and says why. This is practical
context engineering: selection, structure, grounding, and reduction before
generation.

## Outcomes

- `completed`: work research exists, the model produced a valid brief, and it
  recommended an evidence-supported article focus.
- `blocked`: work research is missing, or the brief says available evidence does
  not support a focused article yet. The stage writes a visible brief explaining
  the limit and later stages do not run.
- `failed`: the source artifacts are malformed, the model request fails, or the
  model result fails validation. The runtime records the technical failure in
  `state.json`.

If `resources-report.md` is missing, the stage can still produce a work-only
brief. It records this limitation rather than pretending external knowledge was
available.

## Tests

`tests/test_runtime.py` proves:

- a full research-to-context sequence produces `context-brief.md` with `E1` and
  `R1` references; and
- a missing `research-report.md` blocks without calling the model.

The tests use a fake model client, so they validate the runtime contract without
requiring an API key or live model call.
