# Stage Walkthrough: `research-resources`

`research-resources` turns explicitly supplied local files or URLs into a
traceable `resources-report.md`. It adds external knowledge or personal notes to
the content workflow without letting the runtime search the web on its own.

## Run It

```bash
export OPENAI_API_KEY="..."
python -m personal_ai_agent run "What I learned building tool calling" \
  --repository "/path/to/project-to-research" \
  --resource "/path/to/my/tool-calling-notes.md" \
  --resource "https://example.com/technical-documentation"
```

Repeat `--resource` for each source. V1 accepts readable local UTF-8 text,
HTTP(S) URLs with text/HTML/JSON/XML responses, and a public GitHub repository
URL, whose README is fetched as the resource. Each resource is capped at 512 KB
and the model receives at most 20,000 characters from it.

## Execution Path

`build_content_executor()` in `personal_ai_agent/cli.py` creates a
`ResourceResearchExecutor` with `ResearchResourcesSettings`. The shared
`RoutedStageExecutor` sends only the `research-resources` stage to it.

```text
explicit --resource values
  -> collect_resources()
  -> no values: resources-report.md + skipped
  -> all values inaccessible: resources-report.md + blocked
  -> readable resource bundle
  -> OpenAIResponsesClient.generate_json()
  -> validate_report()
  -> resources-report.md + completed
```

The model client is shared with `research-work`, but the collection rules and
output schema belong to this stage. Sharing the HTTP client removes duplication;
keeping evidence collection separate preserves each capability's responsibility.

## Inputs And Boundaries

- The subject gives the model a lens for interpreting resources.
- `--resource` is the only source inventory in V1.
- A local path is read only when explicitly supplied.
- A URL is fetched only when explicitly supplied.
- The stage does not search for more sources, scrape a repository, or publish.

This is a controlled-generation boundary. It prevents a model from treating its
own broad world knowledge as a source for claims about what the user studied.

## Source IDs And Validation

Every readable source gets an identifier such as `R1`. The model receives a
bounded resource bundle and returns claims with a status and resource IDs:

```json
{
  "status": "Source fact",
  "claim": "A resource-supported technical statement.",
  "resource_ids": ["R1"]
}
```

`validate_report()` rejects a result with the wrong structure, an unknown
resource ID, or a `Source fact` or `Interpretation` without a source. Resource
text is treated as untrusted data, so embedded instructions are not followed.

This does not prove a model interpreted the source perfectly. It gives the
future context builder and reviewer a direct path from a claim to a supplied
resource.

## Stage Outcomes

- `completed`: at least one resource was read, the response passed validation,
  and the report was written.
- `skipped`: no resources were supplied. The report makes that absence explicit;
  later stages can still use work research alone.
- `blocked`: resources were supplied but none could be read. The report records
  why, and the workflow stops rather than replacing the requested sources with
  guesses.
- `failed`: an unexpected fetch, model, or validation error occurred. The
  runtime records the error in `state.json`.

## Tests

`tests/test_runtime.py` checks local resource collection, a successful resource
report using a fake model client, and the no-resource `skipped` path. No test
needs an API key or a live website.
