"""LLM Gateway direct adapter — works with Salesforce internal LLM Gateway.

Uses the /v1/messages endpoint with x-api-key auth and custom CA certs.
Processes requests sequentially with incremental saves for resume support.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .base import BatchAdapter, BatchRequest, BatchResponse

# Map standard model names to gateway model IDs
import re as _re


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown fences and truncation."""
    # Strip markdown code fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```) if present
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Try parsing as-is
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Handle truncated JSON: find the last complete item in a "terms" array
    # Try to close the JSON by finding last complete object and closing brackets
    if '"terms"' in text or '"stories"' in text or '"rules"' in text or '"links"' in text or '"intents"' in text or '"equivalence_groups"' in text:
        # Find last complete }, and close the array and object
        last_complete = text.rfind("},")
        if last_complete == -1:
            last_complete = text.rfind("}")
        if last_complete > 0:
            truncated = text[:last_complete + 1] + "\n  ]\n}"
            try:
                json.loads(truncated)
                return truncated
            except json.JSONDecodeError:
                pass

    return text


GATEWAY_MODEL_MAP = {
    "claude-sonnet-4-6-20250514": "claude-sonnet-4-6",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    "claude-opus-4-6-v1": "claude-opus-4-6-v1",
    "claude-opus-4-7": "claude-opus-4-7",
}


class GatewayDirectAdapter(BatchAdapter):
    """Salesforce LLM Gateway adapter using httpx for direct HTTP calls.

    Reads config from environment:
      - ANTHROPIC_BEDROCK_BASE_URL: gateway URL (strips /bedrock suffix)
      - ANTHROPIC_AUTH_TOKEN: API key for x-api-key header
      - NODE_EXTRA_CA_CERTS: path to CA bundle for TLS verification
    """

    def __init__(self, output_dir: str | Path, rate_limit_delay: float = 1.0):
        try:
            import httpx
        except ImportError:
            raise ImportError("Install httpx: pip install httpx")

        self.output_dir = Path(output_dir)
        self.rate_limit_delay = rate_limit_delay

        base_url = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL", "")
        self.base_url = base_url.replace("/bedrock", "").rstrip("/")
        self.api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        self.cert_path = os.environ.get("NODE_EXTRA_CA_CERTS", "")

        if not self.base_url:
            raise ValueError("ANTHROPIC_BEDROCK_BASE_URL not set")
        if not self.api_key:
            raise ValueError("ANTHROPIC_AUTH_TOKEN not set")

        verify = self.cert_path if self.cert_path and os.path.exists(self.cert_path) else True
        self.http_client = httpx.Client(verify=verify, timeout=120)

    def _resolve_model(self, model: str) -> str:
        return GATEWAY_MODEL_MAP.get(model, model)

    def _call_api(self, prompt: str, model: str, max_tokens: int, system: str = "") -> dict:
        """Make a single messages API call."""
        url = f"{self.base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        payload: dict[str, Any] = {
            "model": self._resolve_model(model),
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        resp = self.http_client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def submit(self, requests: list[BatchRequest]) -> str:
        """Process requests sequentially with incremental saves."""
        batch_id = f"gateway-{int(time.time())}"
        results_dir = self.output_dir / "results" / batch_id
        results_dir.mkdir(parents=True, exist_ok=True)

        manifest = [{"custom_id": r.custom_id, "model": r.model} for r in requests]
        (results_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        total = len(requests)
        success = 0
        errors = 0

        for i, req in enumerate(requests, 1):
            result_file = results_dir / f"{req.custom_id}.json"

            if result_file.exists():
                print(f"  [{i}/{total}] {req.custom_id} — already done, skipping")
                success += 1
                continue

            print(f"  [{i}/{total}] {req.custom_id} — calling gateway...", end="", flush=True)

            try:
                data = self._call_api(
                    prompt=req.prompt,
                    model=req.model or "claude-sonnet-4-6",
                    max_tokens=req.max_tokens,
                    system=req.system,
                )

                raw_text = data["content"][0]["text"] if data.get("content") else ""
                usage = data.get("usage", {})

                try:
                    output = json.loads(_extract_json(raw_text))
                except (json.JSONDecodeError, ValueError):
                    output = {"raw": raw_text}

                result = {
                    "custom_id": req.custom_id,
                    "status": "success",
                    "output": output,
                    "raw_text": raw_text,
                    "usage": {
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                    },
                }
                success += 1
                tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
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

            result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

            if i < total:
                time.sleep(self.rate_limit_delay)

        print(f"\n  Complete: {success} success, {errors} errors")
        print(f"  Results: {results_dir}")
        return batch_id

    def poll(self, batch_id: str) -> str:
        results_dir = self.output_dir / "results" / batch_id
        if not results_dir.exists():
            return "failed"
        manifest_path = results_dir / "manifest.json"
        if not manifest_path.exists():
            return "failed"
        manifest = json.loads(manifest_path.read_text())
        received = len(list(results_dir.glob("*.json"))) - 1
        return "completed" if received >= len(manifest) else "processing"

    def collect(self, batch_id: str) -> list[BatchResponse]:
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
        return "gateway_direct"
