"""Provider-client composition behind a credential-reference boundary.

The current CLI still receives an explicit model name, but it no longer knows
how an OpenAI client is constructed or where the provider credential comes
from. A later API-driven run launcher can resolve the same configuration records
without teaching stages about providers or secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .model_client import ModelClient, OpenAIResponsesClient


@dataclass(frozen=True)
class ProviderRuntimeConfiguration:
    """Executable provider settings expressed only through a credential reference."""

    provider_type: str
    credential_reference: str


class EnvironmentCredentialResolver:
    """Resolve the supported `env:NAME` reference at execution time only."""

    def resolve(self, reference: str) -> str | None:
        """Read an environment value without persisting or returning it to transport code."""
        prefix = "env:"
        if not reference.startswith(prefix) or not reference[len(prefix) :]:
            raise ValueError("Only environment credential references are supported.")
        return os.environ.get(reference[len(prefix) :])


class ModelClientFactory:
    """Create a provider adapter from a policy-approved configuration record."""

    def __init__(self, resolver: EnvironmentCredentialResolver | None = None) -> None:
        """Keep secret lookup replaceable and isolated from stage executors."""
        self._resolver = resolver or EnvironmentCredentialResolver()

    def create(
        self,
        configuration: ProviderRuntimeConfiguration,
        *,
        timeout_seconds: int,
        max_attempts: int,
        max_output_tokens: int,
    ) -> ModelClient:
        """Build the supported provider adapter without exposing its credential."""
        if configuration.provider_type != "openai_responses":
            raise ValueError("The configured provider type is not supported by this runtime.")
        return OpenAIResponsesClient(
            api_key=self._resolver.resolve(configuration.credential_reference),
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            max_output_tokens=max_output_tokens,
        )
