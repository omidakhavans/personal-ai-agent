"""Application records and policy for provider and model configuration.

This module deliberately stores credential *references*, never credential
material. Infrastructure resolves a reference only when a later execution path
needs a provider client.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class ConfigurationError(ValueError):
    """A requested provider or model configuration violates runtime policy."""


class ConfigurationNotFoundError(LookupError):
    """A referenced configuration record does not exist."""


@dataclass(frozen=True)
class ProviderConfiguration:
    """A safe provider record that contains no credential value or endpoint secret."""

    provider_id: str
    display_name: str
    provider_type: str
    credential_reference: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WorkflowModelConfiguration:
    """The one model assignment currently allowed for an entire workflow."""

    workflow_id: str
    provider_id: str
    model: str
    updated_at: datetime


@dataclass(frozen=True)
class ConfigurationAuditEvent:
    """Immutable record of an authenticated configuration change."""

    sequence: int
    action: str
    resource_type: str
    resource_id: str
    actor: str
    occurred_at: datetime
    summary: str


class ConfigurationRepository(Protocol):
    """Persistence port for safe configuration records and their audit history."""

    def list_providers(self) -> tuple[ProviderConfiguration, ...]: ...

    def save_provider(self, provider: ProviderConfiguration, *, actor: str) -> ProviderConfiguration: ...

    def get_provider(self, provider_id: str) -> ProviderConfiguration | None: ...

    def list_workflow_models(self) -> tuple[WorkflowModelConfiguration, ...]: ...

    def save_workflow_model(
        self, configuration: WorkflowModelConfiguration, *, actor: str
    ) -> WorkflowModelConfiguration: ...

    def list_audit_events(self, *, limit: int) -> tuple[ConfigurationAuditEvent, ...]: ...


class ConfigurationApplicationService:
    """Enforce configuration policy before an adapter persists any change."""

    _provider_id = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
    _credential_reference = re.compile(r"^env:[A-Z][A-Z0-9_]{1,127}$")
    _model = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")

    def __init__(self, repository: ConfigurationRepository) -> None:
        """Depend on the configuration port rather than ORM rows or HTTP requests."""
        self._repository = repository

    def providers(self) -> tuple[ProviderConfiguration, ...]:
        """Return only safe provider metadata and credential references."""
        return self._repository.list_providers()

    def save_provider(
        self,
        *,
        provider_id: str,
        display_name: str,
        credential_reference: str,
        enabled: bool,
        actor: str,
    ) -> ProviderConfiguration:
        """Create or update the only currently supported provider kind."""
        if not self._provider_id.fullmatch(provider_id):
            raise ConfigurationError("Provider IDs must use lowercase letters, digits, and hyphens.")
        if not display_name.strip() or len(display_name.strip()) > 120:
            raise ConfigurationError("Provider display names must contain 1 to 120 characters.")
        if not self._credential_reference.fullmatch(credential_reference):
            raise ConfigurationError("Credential references must be environment references such as env:OPENAI_API_KEY.")
        previous = self._repository.get_provider(provider_id)
        now = datetime.now(UTC)
        return self._repository.save_provider(
            ProviderConfiguration(
                provider_id=provider_id,
                display_name=display_name.strip(),
                provider_type="openai_responses",
                credential_reference=credential_reference,
                enabled=enabled,
                created_at=previous.created_at if previous else now,
                updated_at=now,
            ),
            actor=actor,
        )

    def workflow_models(self) -> tuple[WorkflowModelConfiguration, ...]:
        """Return model assignments for workflows that the runtime actually has."""
        return self._repository.list_workflow_models()

    def save_workflow_model(
        self, *, workflow_id: str, provider_id: str, model: str, actor: str
    ) -> WorkflowModelConfiguration:
        """Assign one enabled provider/model pair to the known content workflow."""
        if workflow_id != "content":
            raise ConfigurationError("Only the content workflow exists in this runtime.")
        provider = self._repository.get_provider(provider_id)
        if provider is None:
            raise ConfigurationNotFoundError("The selected provider does not exist.")
        if not provider.enabled:
            raise ConfigurationError("The selected provider is disabled.")
        if not self._model.fullmatch(model):
            raise ConfigurationError("Model names contain unsupported characters or are too long.")
        return self._repository.save_workflow_model(
            WorkflowModelConfiguration(
                workflow_id=workflow_id,
                provider_id=provider_id,
                model=model,
                updated_at=datetime.now(UTC),
            ),
            actor=actor,
        )

    def audit_events(self, *, limit: int = 50) -> tuple[ConfigurationAuditEvent, ...]:
        """Expose bounded audit history for operators, never technical logs."""
        if not 1 <= limit <= 100:
            raise ConfigurationError("Audit event limit must be between 1 and 100.")
        return self._repository.list_audit_events(limit=limit)
