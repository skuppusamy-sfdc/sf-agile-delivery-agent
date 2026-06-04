"""OpenAI Batch API adapter — 50% cost reduction.

Requires: pip install openai
Set OPENAI_API_KEY environment variable.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .base import BatchAdapter, BatchRequest, BatchResponse


class OpenAIBatchAdapter(BatchAdapter):
    """OpenAI Batch API.

    Submits requests for async processing. Results within 24 hours at 50% cost.
    """

    def __init__(self, api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Install openai SDK: pip install openai")

        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def submit(self, requests: list[BatchRequest]) -> str:
        lines = []
        for req in requests:
            messages = []
            if req.system:
                messages.append({"role": "system", "content": req.system})
            messages.append({"role": "user", "content": req.prompt})

            lines.append(json.dumps({
                "custom_id": req.custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": req.model or "gpt-4o",
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
            }))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(lines))
            tmp_path = f.name

        with open(tmp_path, "rb") as f:
            uploaded = self.client.files.create(file=f, purpose="batch")

        batch = self.client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )

        Path(tmp_path).unlink(missing_ok=True)
        print(f"  Submitted batch: {batch.id} ({len(requests)} requests)")
        return batch.id

    def poll(self, batch_id: str) -> str:
        batch = self.client.batches.retrieve(batch_id)
        status_map = {
            "validating": "pending",
            "in_progress": "processing",
            "finalizing": "processing",
            "completed": "completed",
            "failed": "failed",
            "expired": "failed",
            "cancelled": "failed",
            "cancelling": "failed",
        }
        return status_map.get(batch.status, "pending")

    def collect(self, batch_id: str) -> list[BatchResponse]:
        batch = self.client.batches.retrieve(batch_id)
        if not batch.output_file_id:
            return []

        content = self.client.files.content(batch.output_file_id)
        results = []

        for line in content.text.strip().split("\n"):
            item = json.loads(line)
            custom_id = item["custom_id"]
            response = item.get("response", {})

            if response.get("status_code") == 200:
                body = response.get("body", {})
                choices = body.get("choices", [])
                raw_text = choices[0]["message"]["content"] if choices else ""
                try:
                    output = json.loads(raw_text)
                except json.JSONDecodeError:
                    output = {"raw": raw_text}
                usage = body.get("usage", {})
                results.append(BatchResponse(
                    custom_id=custom_id,
                    status="success",
                    output=output,
                    raw_text=raw_text,
                    error=None,
                    usage={
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                    },
                ))
            else:
                error_body = item.get("error", {})
                results.append(BatchResponse(
                    custom_id=custom_id,
                    status="error",
                    output=None,
                    raw_text="",
                    error=error_body.get("message", "Unknown error"),
                    usage=None,
                ))

        return results

    def provider_name(self) -> str:
        return "openai_batch"
