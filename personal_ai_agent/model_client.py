"""Small, provider-specific model boundary used by implemented stages."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Protocol


class ModelClient(Protocol):
    """Generate one structured JSON object from bounded stage input."""

    def generate_json(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a JSON object that conforms to the supplied schema."""


class OpenAIResponsesClient:
    """Minimal SDK-free client for the OpenAI Responses API."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_seconds: int = 60,
        max_output_tokens: int = 1_600,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.max_attempts = max_attempts

    def generate_json(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required to run a real model stage.")
        if self.timeout_seconds <= 0 or self.max_output_tokens <= 0 or self.max_attempts <= 0:
            raise RuntimeError("Model client limits must be positive.")

        payload = {
            "model": model,
            "max_output_tokens": self.max_output_tokens,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": instructions}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_text}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        response_payload = self._send_with_retries(request)

        output_text = _response_output_text(response_payload)
        try:
            return json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Model response was not valid JSON.") from exc

    def _send_with_retries(self, request: urllib.request.Request) -> dict[str, Any]:
        for attempt in range(1, self.max_attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if not retryable or attempt == self.max_attempts:
                    raise RuntimeError(f"OpenAI API request failed (HTTP {exc.code}).") from exc
            except urllib.error.URLError as exc:
                # A timeout or connection drop can happen after the provider
                # accepted the request, so automatic retry could duplicate paid work.
                raise RuntimeError("OpenAI API request could not be completed.") from exc
            time.sleep(0.5 * attempt)
        raise RuntimeError("OpenAI API request could not be completed.")  # pragma: no cover


def _response_output_text(payload: dict[str, Any]) -> str:
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text":
                return content["text"]
    raise RuntimeError("OpenAI API response did not contain output text.")
