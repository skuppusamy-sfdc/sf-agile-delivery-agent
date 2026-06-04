"""Anthropic Direct adapter — sequential messages.create() calls.

Works through any Anthropic-compatible proxy (LLM Gateway, Bedrock, etc.)
where the Batch API endpoint is not available.

Uses standard ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY for auth.
Respects ANTHROPIC_BEDROCK_BASE_URL if set.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .base import BatchAdapter, BatchRequest, BatchResponse


class AnthropicDirectAdapter(BatchAdapter):
    """Sequential messages.create() calls through any Anthropic-compatible endpoint.

    Saves results to disk incrementally so progress is not lost on interruption.
    Supports resume from partial completion.
    """

    def __init__(self, output_dir: str | Path, rate_limit_delay: float = 1.0):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Install anthropic SDK: pip install anthropic")

        self.output_dir = Path(output_dir)
        self.rate_limit_delay = rate_limit_delay

        # The SDK auto-detects ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY,
        # and ANTHROPIC_BEDROCK_BASE_URL from environment
        self.client = Anthropic()

    def submit(self, requests: list[BatchRequest]) -> str:
        """Process requests sequentially with incremental saves."""
        batch_id = f"direct-{int(time.time())}"
        results_dir = self.output_dir / "results" / batch_id
        results_dir.mkdir(parents=True, exist_ok=True)

        # Save manifest
        manifest = [{"custom_id": r.custom_id, "model": r.model} for r in requests]
        (results_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        total = len(requests)
        success = 0
        errors = 0

        for i, req in enumerate(requests, 1):
            result_file = results_dir / f"{req.custom_id}.json"

            # Skip if already processed (resume support)
            if result_file.exists():
                print(f"  [{i}/{total}] {req.custom_id} — already done, skipping")
                success += 1
                continue

            print(f"  [{i}/{total}] {req.custom_id} — calling API...", end="", flush=True)

            try:
                messages = [{"role": "user", "content": req.prompt}]
                kwargs: dict[str, Any] = {
                    "model": req.model or "claude-sonnet-4-6-20250514",
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
                    "messages": messages,
                }
                if req.system:
                    kwargs["system"] = req.system

                msg = self.client.messages.create(**kwargs)
                raw_text = msg.content[0].text if msg.content else ""

                try:
                    output = json.loads(raw_text)
                except json.JSONDecodeError:
                    output = {"raw": raw_text}

                result = {
                    "custom_id": req.custom_id,
                    "status": "success",
                    "output": output,
                    "raw_text": raw_text,
                    "usage": {
                        "input_tokens": msg.usage.input_tokens,
                        "output_tokens": msg.usage.output_tokens,
                    },
                }
                success += 1
                tokens = msg.usage.input_tokens + msg.usage.output_tokens
                print(f" done ({tokens:,} tokens)")

            except Exception as e:
                result = {
                    "custom_id": req.custom_id,
                    "status": "error",
                    "output": None,
                    "raw_text": "",
                    "error": str(e),
                }
                errors += 1
                print(f" ERROR: {e}")

            # Save incrementally
            result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

            # Rate limiting
            if i < total:
                time.sleep(self.rate_limit_delay)

        print(f"\n  Complete: {success} success, {errors} errors")
        print(f"  Results saved to: {results_dir}")
        return batch_id

    def poll(self, batch_id: str) -> str:
        """Direct adapter is synchronous — always completed after submit."""
        results_dir = self.output_dir / "results" / batch_id
        if not results_dir.exists():
            return "failed"

        manifest_path = results_dir / "manifest.json"
        if not manifest_path.exists():
            return "failed"

        manifest = json.loads(manifest_path.read_text())
        expected = len(manifest)
        received = len(list(results_dir.glob("*.json"))) - 1  # minus manifest

        if received >= expected:
            return "completed"
        return "processing"

    def collect(self, batch_id: str) -> list[BatchResponse]:
        """Read results from disk."""
        results_dir = self.output_dir / "results" / batch_id
        results = []

        for result_file in sorted(results_dir.glob("*.json")):
            if result_file.name == "manifest.json":
                continue

            data = json.loads(result_file.read_text(encoding="utf-8"))
            results.append(BatchResponse(
                custom_id=data["custom_id"],
                status=data["status"],
                output=data.get("output"),
                raw_text=data.get("raw_text", ""),
                error=data.get("error"),
                usage=data.get("usage"),
            ))

        return results

    def provider_name(self) -> str:
        return "anthropic_direct"
