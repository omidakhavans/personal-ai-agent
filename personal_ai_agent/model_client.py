"""Small, provider-specific model boundary used by implemented stages."""

from __future__ import annotations

import json
import os
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

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

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

        payload = {
            "model": model,
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
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenAI API request failed (HTTP {exc.code}).") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("OpenAI API request could not be completed.") from exc

        output_text = _response_output_text(response_payload)
        try:
            return json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Model response was not valid JSON.") from exc


def _response_output_text(payload: dict[str, Any]) -> str:
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text":
                return content["text"]
    raise RuntimeError("OpenAI API response did not contain output text.")
