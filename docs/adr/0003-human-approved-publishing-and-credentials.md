# ADR 0003: Keep Publication Human-Approved And Credentials Outside Run State

Status: Proposed for Phase 3.

## Context

The current runtime never publishes. It fingerprints a reviewed article and
requires an explicit owner approval before it creates social drafts. Phase 3
will add external publishing integrations and therefore introduces irreversible
effects and long-lived credentials.

## Decision

Publication will remain a separate application command after review and an
explicit human approval tied to the exact content artifact. Publisher adapters
must receive an idempotency identity and record each external attempt.

Credentials will be stored as encrypted values with key references and rotation
metadata. Plaintext credentials, access tokens, and provider secrets must not
be stored in run records, artifacts, events, ordinary logs, or API responses.

## Consequences

- Drafting and publishing remain different lifecycle states.
- A retry cannot silently publish a changed or unapproved artifact.
- Credential access needs a key-management interface, redaction tests, and
  restrictive operator permissions.
- Platform adapters require more tests than read-only research tools because
  they change an external system.
