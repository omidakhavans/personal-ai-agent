# Stage Walkthrough: `approve-social`

`approve-social` is an explicit human checkpoint after a passing blog review
and before any social drafts are generated. It writes `approval.md` and pauses
the run with `awaiting_approval`.

## Why This Is A Runtime Feature

No model decides approval. `SocialApprovalExecutor` in
`personal_ai_agent/approval.py` writes an approval request, while
`Orchestrator.approve_social()` in `personal_ai_agent/runtime.py` records the
owner's later decision and resumes the remaining deterministic stages.

```text
review ready
  -> approval.md says awaiting_human_approval
  -> owner runs approve-social
  -> approval.md says approved
  -> LinkedIn and X drafts may run
```

From the project root, approve a paused run with:

```bash
python -m personal_ai_agent approve-social <run-id> \
  --notes "Reviewed the source boundaries."
```

The command does not publish anything. It records the matching reviewed blog
fingerprint, so approval belongs to that exact article version before it can be
transformed into further drafts.

## State Design

`awaiting_approval` differs from `blocked`:

- `blocked` means better inputs or revision are required before continuing.
- `awaiting_approval` means the automated quality gate passed and a human
  decision is intentionally outstanding.

This is ordinary state-machine design applied to an agent workflow. The
agent-specific lesson is that important judgment should remain visible and
auditable instead of being silently implied by a model response.
