"""Anthropic Messages Batch API adapter — 50% cost reduction.

Requires: pip install anthropic
Set ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .base import BatchAdapter, BatchRequest, BatchResponse


class AnthropicBatchAdapter(BatchAdapter):
    """Anthropic Messages Batch API.

    Submits requests as a batch for asynchronous processing.
    Results available within minutes to hours at 50% cost reduction.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Install anthropic SDK: pip install anthropic")

        self.client = Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=base_url,
        )

    def _build_batch_requests(self, requests: list[BatchRequest]) -> list[dict]:
        batch_requests = []
        for req in requests:
            messages = [{"role": "user", "content": req.prompt}]
            params: dict[str, Any] = {
                "model": req.model or "claude-sonnet-4-6-20250514",
                "max_tokens": req.max_tokens,
                "temperature": req.temperature,
                "messages": messages,
            }
            if req.system:
                params["system"] = req.system
            batch_requests.append({
                "custom_id": req.custom_id,
                "params": params,
            })
        return batch_requests

    def submit(self, requests: list[BatchRequest]) -> str:
        import time

        batch_requests = self._build_batch_requests(requests)

        # Split into sub-batches of 10 requests to avoid payload size limits
        SUB_BATCH_SIZE = 10
        batch_ids = []

        for i in range(0, len(batch_requests), SUB_BATCH_SIZE):
            chunk = batch_requests[i:i + SUB_BATCH_SIZE]
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    batch = self.client.messages.batches.create(requests=chunk)
                    batch_ids.append(batch.id)
                    print(f"  Submitted sub-batch {len(batch_ids)}: {batch.id} ({len(chunk)} requests)")
                    break
                except Exception as e:
                    error_str = str(e)
                    if attempt < max_retries - 1:
                        wait = 2 ** (attempt + 1)
                        print(f"  Retry {attempt + 1}/{max_retries} after {wait}s...")
                        time.sleep(wait)
                    else:
                        raise
            time.sleep(1)

        # Store all batch IDs joined by comma for tracking
        combined_id = ",".join(batch_ids)
        self._batch_ids = batch_ids
        print(f"  Total: {len(batch_ids)} sub-batches, {len(requests)} requests")
        return combined_id

    def poll(self, batch_id: str) -> str:
        ids = batch_id.split(",")
        statuses = []
        for bid in ids:
            batch = self.client.messages.batches.retrieve(bid)
            statuses.append(batch.processing_status)

        if all(s == "ended" for s in statuses):
            return "completed"
        if any(s in ("canceling", "canceled") for s in statuses):
            return "failed"
        return "processing"

    def collect(self, batch_id: str) -> list[BatchResponse]:
        ids = batch_id.split(",")
        results = []
        for bid in ids:
            for result in self.client.messages.batches.results(bid):
                if result.result.type == "succeeded":
                    msg = result.result.message
                    raw_text = msg.content[0].text if msg.content else ""
                    try:
                        output = json.loads(raw_text)
                    except json.JSONDecodeError:
                        output = {"raw": raw_text}
                    results.append(BatchResponse(
                        custom_id=result.custom_id,
                        status="success",
                        output=output,
                        raw_text=raw_text,
                        error=None,
                        usage={
                            "input_tokens": msg.usage.input_tokens,
                            "output_tokens": msg.usage.output_tokens,
                        },
                    ))
                else:
                    results.append(BatchResponse(
                        custom_id=result.custom_id,
                        status="error",
                        output=None,
                        raw_text="",
                        error=str(getattr(result.result, "error", "Unknown error")),
                        usage=None,
                    ))
        return results

    def provider_name(self) -> str:
        return "anthropic_batch"
