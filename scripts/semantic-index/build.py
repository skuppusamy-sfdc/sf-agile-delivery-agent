#!/usr/bin/env python3
"""
Semantic Index Builder — LLM-at-build-time, tool-agnostic.

Orchestrates the full pipeline:
  1. Load corpus (story markdown files)
  2. Prepare batch requests (chunk + render prompts)
  3. Submit to LLM provider (via adapter)
  4. Collect responses
  5. Assemble into final JSON indexes

Usage:
    python -m semantic-index.build                        # Build all indexes
    python -m semantic-index.build --index glossary       # Build one index
    python -m semantic-index.build --dry-run              # Show request count without submitting
    python -m semantic-index.build --resume BATCH_ID      # Collect results from prior submission
    python -m semantic-index.build --adapter file_based   # Override adapter

Zero external dependencies for file_based adapter. API adapters need their respective SDKs.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    import yaml
    def load_config(path):
        return yaml.safe_load(path.read_text())
except ImportError:
    import re as _re
    def load_config(path):
        """Minimal YAML parser for our flat config (one level of nesting)."""
        text = path.read_text()
        config = {}
        current_key = None
        for line in text.split("\n"):
            stripped = _re.sub(r"#.*$", "", line).rstrip()
            if not stripped:
                continue
            indent = len(stripped) - len(stripped.lstrip())
            content = stripped.strip()
            if content.startswith("- "):
                val = content[2:].strip()
                if current_key and isinstance(config.get(current_key), list):
                    config[current_key].append(val)
                continue
            if ":" not in content:
                continue
            key, _, val = content.partition(":")
            key, val = key.strip(), val.strip().strip("'\"")
            if indent == 0:
                if val:
                    config[key] = int(val) if val.isdigit() else val
                else:
                    config[key] = {}
                current_key = key
            elif current_key and isinstance(config.get(current_key), dict):
                config[current_key][key] = int(val) if val.isdigit() else val
        return config


INDEX_NAMES = [
    "glossary",
    "story_summaries",
    "business_rules",
    "semantic_similarity",
    "cross_story_links",
    "intent_mapping",
]

INDEX_OUTPUT_FILES = {
    "glossary": "SEMANTIC-GLOSSARY.json",
    "story_summaries": "STORY-SUMMARIES.json",
    "business_rules": "BUSINESS-RULES.json",
    "semantic_similarity": "SEMANTIC-SIMILARITY.json",
    "cross_story_links": "CROSS-STORY-LINKS.json",
    "intent_mapping": "INTENT-MAP.json",
}


def get_adapter(adapter_name: str, output_dir: Path):
    """Instantiate the requested adapter."""
    if adapter_name == "file_based":
        from adapters.file_based import FileBasedAdapter
        return FileBasedAdapter(output_dir)
    elif adapter_name == "anthropic_batch":
        from adapters.anthropic_batch import AnthropicBatchAdapter
        return AnthropicBatchAdapter()
    elif adapter_name == "anthropic_direct":
        from adapters.anthropic_direct import AnthropicDirectAdapter
        return AnthropicDirectAdapter(output_dir)
    elif adapter_name == "gateway_direct":
        from adapters.gateway_direct import GatewayDirectAdapter
        return GatewayDirectAdapter(output_dir)
    elif adapter_name == "openai_batch":
        from adapters.openai_batch import OpenAIBatchAdapter
        return OpenAIBatchAdapter()
    else:
        raise ValueError(f"Unknown adapter: {adapter_name}. Options: file_based, anthropic_direct, anthropic_batch, openai_batch")


def build_index(
    index_name: str,
    stories: list[dict],
    config: dict,
    adapter,
    prompts_dir: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> str | None:
    """Build a single semantic index. Returns batch_id if submitted."""
    from prepare import prepare_requests

    print(f"\n{'=' * 40}")
    print(f"  INDEX: {index_name}")
    print(f"{'=' * 40}")

    batch_size = config.get("batch_size", {}).get(index_name, 30)
    model = config.get("models", {}).get(index_name, "claude-sonnet-4-6-20250514")
    max_tokens = config.get("max_tokens", {}).get(index_name, 4096)

    requests = prepare_requests(
        index_name=index_name,
        stories=stories,
        prompts_dir=prompts_dir,
        batch_size=batch_size,
        model=model,
        max_tokens=max_tokens,
    )

    print(f"  Stories: {len(stories)}")
    print(f"  Batch size: {batch_size}")
    print(f"  Requests: {len(requests)}")
    print(f"  Model: {model}")

    if dry_run:
        print(f"  [DRY RUN] Would submit {len(requests)} requests")
        return None

    batch_id = adapter.submit(requests)
    print(f"  Batch ID: {batch_id}")
    return batch_id


def collect_and_assemble(
    index_name: str,
    batch_id: str,
    adapter,
    index_output_dir: Path,
):
    """Poll for completion, collect results, assemble index."""
    from assemble import assemble_index, write_index

    print(f"\n  Polling batch {batch_id}...")
    while True:
        status = adapter.poll(batch_id)
        if status == "completed":
            break
        if status == "failed":
            print(f"  ERROR: Batch {batch_id} failed.")
            return
        print(f"  Status: {status} — waiting...")
        time.sleep(10)

    print(f"  Collecting responses...")
    responses = adapter.collect(batch_id)

    success_count = sum(1 for r in responses if r.status == "success")
    error_count = sum(1 for r in responses if r.status == "error")
    print(f"  Results: {success_count} success, {error_count} errors")

    if success_count == 0:
        print(f"  ERROR: No successful responses. Cannot assemble index.")
        return

    print(f"  Assembling index...")
    index_data = assemble_index(index_name, responses)

    output_file = index_output_dir / INDEX_OUTPUT_FILES[index_name]
    write_index(index_data, output_file)


def main():
    parser = argparse.ArgumentParser(description="Build semantic indexes using LLM-at-build-time")
    parser.add_argument("--index", choices=INDEX_NAMES, help="Build a specific index (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted")
    parser.add_argument("--resume", metavar="BATCH_ID", help="Collect results from a prior batch")
    parser.add_argument("--adapter", help="Override adapter from config")
    parser.add_argument("--config", default=str(Path(__file__).parent / "config.yaml"), help="Config file path")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}")
        return 1

    config = load_config(config_path)

    sprints_dir = PROJECT_ROOT / config.get("corpus", {}).get("sprints_dir", "knowledge/sprints")
    output_dir = PROJECT_ROOT / config.get("output_dir", ".semantic-index-cache")
    index_output_dir = PROJECT_ROOT / config.get("index_output_dir", "knowledge")
    prompts_dir = Path(__file__).parent / "prompts"

    adapter_name = args.adapter or config.get("adapter", "file_based")
    adapter = get_adapter(adapter_name, output_dir)

    print(f"\n=== Semantic Index Builder ===")
    print(f"  Adapter: {adapter.provider_name()}")
    print(f"  Corpus: {sprints_dir}")
    print(f"  Output: {index_output_dir}")

    if args.resume:
        index_name = args.index
        if not index_name:
            print("ERROR: --resume requires --index to specify which index to assemble")
            return 1
        collect_and_assemble(index_name, args.resume, adapter, index_output_dir)
        return 0

    from prepare import load_corpus
    print(f"\n  Loading corpus...")
    stories = load_corpus(sprints_dir)
    print(f"  Loaded {len(stories)} stories")

    if not stories:
        print("  ERROR: No stories found.")
        return 1

    indexes_to_build = [args.index] if args.index else INDEX_NAMES

    for index_name in indexes_to_build:
        batch_id = build_index(
            index_name=index_name,
            stories=stories,
            config=config,
            adapter=adapter,
            prompts_dir=prompts_dir,
            output_dir=output_dir,
            dry_run=args.dry_run,
        )

        if batch_id and adapter_name != "file_based":
            collect_and_assemble(index_name, batch_id, adapter, index_output_dir)

    if adapter_name == "file_based" and not args.dry_run:
        print(f"\n  File-based adapter: prompts written to {output_dir}/requests/")
        print(f"  Process them through your LLM, save responses, then run:")
        print(f"    python -m semantic_index.build --resume BATCH_ID --index INDEX_NAME")

    print("\n  Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
