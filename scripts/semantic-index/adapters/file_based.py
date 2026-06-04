"""File-based adapter — zero API dependencies.

Writes prompts to text files. User processes them through any LLM
(web UI, API, local model) and saves JSON responses back.
This is the most portable adapter — works with any provider.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .base import BatchAdapter, BatchRequest, BatchResponse


class FileBasedAdapter(BatchAdapter):
    """Write prompts to files; read responses from files.

    Workflow:
        1. submit() writes prompts to output/requests/{batch_id}/
        2. User processes each .txt prompt through their chosen LLM
        3. User saves JSON responses to output/responses/{batch_id}/
        4. collect() reads response files and returns structured results
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    def submit(self, requests: list[BatchRequest]) -> str:
        batch_id = f"batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        batch_dir = self.output_dir / "requests" / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        manifest = []
        for req in requests:
            prompt_file = batch_dir / f"{req.custom_id}.txt"
            content = ""
            if req.system:
                content += f"[SYSTEM]\n{req.system}\n\n[USER]\n"
            content += req.prompt
            prompt_file.write_text(content, encoding="utf-8")
            manifest.append({
                "custom_id": req.custom_id,
                "file": prompt_file.name,
                "model": req.model,
                "max_tokens": req.max_tokens,
            })

        manifest_path = batch_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        response_dir = self.output_dir / "responses" / batch_id
        response_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'=' * 60}")
        print(f"  BATCH READY: {batch_dir}")
        print(f"  {len(requests)} prompts written as .txt files")
        print(f"")
        print(f"  Process each .txt file through any LLM.")
        print(f"  Save JSON responses to:")
        print(f"    {response_dir}/")
        print(f"  Use matching filenames: {{custom_id}}.json")
        print(f"{'=' * 60}\n")

        return batch_id

    def poll(self, batch_id: str) -> str:
        response_dir = self.output_dir / "responses" / batch_id
        request_dir = self.output_dir / "requests" / batch_id

        if not response_dir.exists():
            return "pending"

        manifest_path = request_dir / "manifest.json"
        if not manifest_path.exists():
            return "failed"

        manifest = json.loads(manifest_path.read_text())
        expected = len(manifest)
        received = len(list(response_dir.glob("*.json")))

        if received >= expected:
            return "completed"
        if received > 0:
            return "processing"
        return "pending"

    def collect(self, batch_id: str) -> list[BatchResponse]:
        response_dir = self.output_dir / "responses" / batch_id
        results = []

        for resp_file in sorted(response_dir.glob("*.json")):
            custom_id = resp_file.stem
            raw_text = resp_file.read_text(encoding="utf-8")
            try:
                output = json.loads(raw_text)
                results.append(BatchResponse(
                    custom_id=custom_id,
                    status="success",
                    output=output,
                    raw_text=raw_text,
                    error=None,
                    usage=None,
                ))
            except json.JSONDecodeError as e:
                results.append(BatchResponse(
                    custom_id=custom_id,
                    status="error",
                    output=None,
                    raw_text=raw_text,
                    error=f"Invalid JSON: {e}",
                    usage=None,
                ))

        return results

    def provider_name(self) -> str:
        return "file_based"
