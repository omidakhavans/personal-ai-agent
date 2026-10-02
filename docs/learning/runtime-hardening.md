# Runtime Hardening

This guide explains the protections added after the first real research stages.
They are intentionally ordinary Python and operating-system techniques. Their
importance is amplified in an AI workflow because model calls can be costly,
slow, non-deterministic, and capable of receiving text from many sources.

## 1. Keep Shareable Artifacts Separate From Local Resume Data

Files: `personal_ai_agent/cli.py`, `personal_ai_agent/state.py`, and
`personal_ai_agent/privacy.py`

`state.json` is an audit artifact. It can be inspected, shared, or committed by
mistake, so it stores a label such as `local repository: project` rather than an
absolute user-machine path. The actual paths needed by `resume` are stored in
`runs/.runtime-config/<run-id>.json`, which is ignored by Git and written with
owner-only permissions.

Why this is ordinary engineering: configuration and public output often have
different confidentiality requirements.

Why it matters for agents: runs accumulate inputs and outputs over time. A
single convenient state file can otherwise become an accidental record of every
local path or selected source.

`redact_sensitive_text()` also removes several common credential shapes before
collected text reaches the model. This is deliberately called *best effort*.
Never treat a regular expression as proof that a repository is safe to send to a
remote service.

## 2. Constrain The Resource Tool

Files: `personal_ai_agent/resource_fetch.py` and
`personal_ai_agent/research_resources.py`

The resource tool accepts only explicit public HTTPS URLs. It resolves the host,
rejects loopback/private/link-local/reserved addresses, and applies the same test
to redirects. It also caps redirects and bytes read.

Why this is ordinary engineering: a network client needs input validation,
timeouts, and size limits.

Why it matters for agents: a later agent may get URLs from a document, issue, or
model suggestion. Without this boundary, a URL can make the local machine fetch
an internal endpoint; the fetched result might then be placed into a model
prompt. This class of risk is commonly called server-side request forgery.

## 3. Make State A Durable Checkpoint

Files: `personal_ai_agent/state.py` and `personal_ai_agent/runtime.py`

`write_state()` writes JSON to a temporary file, flushes it, then atomically
replaces `state.json`. `read_state()` validates the expected shape and returns a
clear error for corrupt data. The state format has a version and migrates the
earlier local format by adding stage attempt counts.

Why this is ordinary engineering: a process can stop halfway through a write.

Why it matters for agents: `state.json` controls whether a model stage is run,
skipped, or resumed. A half-written checkpoint could either lose work or cause a
duplicate model call.

`run_lock()` also prevents two CLI processes from advancing the same run at once.
Each stage records `attempts`; resuming an interrupted `running` stage is an
explicit retry and can create another model call. The runtime does not pretend a
retry is free or identical to the first attempt.

## 4. Treat Artifacts As Part Of The Contract

Files: `personal_ai_agent/stages.py` and `personal_ai_agent/runtime.py`

Each `Stage` has a fixed artifact name. After a non-failed stage returns, the
orchestrator checks that it returned that exact name and wrote a non-empty regular
file inside the run directory. It repeats that check before resuming past earlier
completed work.

Why this is ordinary engineering: return values and files can disagree after a
bug, crash, or partial deployment.

Why it matters for agents: later stages reason over artifacts. A state transition
that says “research completed” is not enough when `context-brief` needs a real
research report to ground its next model call.

## 5. Bound Model Operations

File: `personal_ai_agent/model_client.py`

The raw Responses API client has a fixed timeout, output-token cap, and a small
retry policy for rate-limit and server errors. It does not automatically retry a
connection failure because the provider may have accepted the request before the
client lost contact. It never retries permanent client errors.

Why this is ordinary engineering: remote APIs need predictable latency and
failure handling.

Why it matters for agents: an unconstrained model call can exceed a run’s time or
cost expectations. A retry policy must be conservative because a request may
have been processed even when the client did not receive the response.

## Exercises

1. Change the model output cap in `OpenAIResponsesClient`, then update the test
   that inspects the request payload.
2. Add one credential format to `redact_sensitive_text()` and write a regression
   test that confirms it never reaches a fake model client.
3. Add a test showing that an artifact symlink outside the run directory causes
   resume to stop safely.
4. Add a controlled command-line switch that disables remote-resource loading,
   then make the resource stage record a `blocked` explanation.
5. Replace the fixed retry delay with a bounded exponential backoff and explain
   why it must still have an upper limit.
