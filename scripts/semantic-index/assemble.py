"""Assemble LLM responses into final index JSON files.

Handles deduplication, merging, conflict resolution, and validation.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from adapters.base import BatchResponse


def assemble_glossary(responses: list[BatchResponse]) -> dict[str, Any]:
    """Merge glossary responses into a unified deduplicated glossary."""
    all_terms: dict[str, dict] = {}

    for resp in responses:
        if resp.status != "success" or not resp.output:
            continue
        terms = resp.output.get("terms", [])
        for term in terms:
            key = term.get("term", "").upper().strip()
            if not key:
                continue
            if key in all_terms:
                existing = all_terms[key]
                existing_stories = set(existing.get("found_in", []))
                new_stories = set(term.get("found_in", []))
                existing["found_in"] = sorted(existing_stories | new_stories)
                existing_synonyms = set(existing.get("synonyms", []))
                new_synonyms = set(term.get("synonyms", []))
                existing["synonyms"] = sorted(existing_synonyms | new_synonyms)
            else:
                all_terms[key] = term

    sorted_terms = sorted(all_terms.values(), key=lambda t: t.get("term", ""))
    return {
        "index_type": "glossary",
        "total_terms": len(sorted_terms),
        "terms": sorted_terms,
    }


def assemble_story_summaries(responses: list[BatchResponse]) -> dict[str, Any]:
    """Merge story summary responses into a unified index."""
    all_stories: dict[str, dict] = {}

    for resp in responses:
        if resp.status != "success" or not resp.output:
            continue
        stories = resp.output.get("stories", [])
        for story in stories:
            sid = story.get("id", "")
            if sid:
                all_stories[sid] = story

    sorted_stories = sorted(all_stories.values(), key=lambda s: s.get("id", ""))
    return {
        "index_type": "story_summaries",
        "total_stories": len(sorted_stories),
        "stories": sorted_stories,
    }


def assemble_business_rules(responses: list[BatchResponse]) -> dict[str, Any]:
    """Merge business rule extraction responses."""
    all_rules: list[dict] = []
    seen_ids: set[str] = set()

    for resp in responses:
        if resp.status != "success" or not resp.output:
            continue
        rules = resp.output.get("rules", [])
        for rule in rules:
            rule_id = rule.get("rule_id", "")
            if rule_id and rule_id not in seen_ids:
                seen_ids.add(rule_id)
                all_rules.append(rule)

    all_rules.sort(key=lambda r: r.get("story_id", "") + r.get("rule_id", ""))
    return {
        "index_type": "business_rules",
        "total_rules": len(all_rules),
        "rules": all_rules,
    }


def assemble_semantic_similarity(responses: list[BatchResponse]) -> dict[str, Any]:
    """Merge semantic similarity group responses."""
    groups: dict[str, dict] = {}

    for resp in responses:
        if resp.status != "success" or not resp.output:
            continue
        for group in resp.output.get("equivalence_groups", []):
            canonical = group.get("canonical", "").lower().strip()
            if not canonical:
                continue
            if canonical in groups:
                existing_variants = {v["phrase"] for v in groups[canonical].get("variants", [])}
                for v in group.get("variants", []):
                    if v["phrase"] not in existing_variants:
                        groups[canonical]["variants"].append(v)
            else:
                groups[canonical] = group

    sorted_groups = sorted(groups.values(), key=lambda g: g.get("canonical", ""))
    return {
        "index_type": "semantic_similarity",
        "total_groups": len(sorted_groups),
        "equivalence_groups": sorted_groups,
    }


def assemble_cross_story_links(responses: list[BatchResponse]) -> dict[str, Any]:
    """Merge cross-story link responses, deduplicating edges."""
    seen_edges: set[str] = set()
    all_links: list[dict] = []

    for resp in responses:
        if resp.status != "success" or not resp.output:
            continue
        for link in resp.output.get("links", []):
            from_s = link.get("from_story", "")
            to_s = link.get("to_story", "")
            rel = link.get("relationship", "")
            edge_key = f"{from_s}|{to_s}|{rel}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                all_links.append(link)

    all_links.sort(key=lambda l: l.get("from_story", ""))
    return {
        "index_type": "cross_story_links",
        "total_links": len(all_links),
        "links": all_links,
    }


def assemble_intent_mapping(responses: list[BatchResponse]) -> dict[str, Any]:
    """Merge intent mapping responses."""
    all_intents: dict[str, dict] = {}

    for resp in responses:
        if resp.status != "success" or not resp.output:
            continue
        for intent in resp.output.get("intents", []):
            intent_id = intent.get("intent_id", "")
            if not intent_id:
                continue
            if intent_id in all_intents:
                existing = all_intents[intent_id]
                existing_queries = set(existing.get("query_variations", []))
                new_queries = set(intent.get("query_variations", []))
                existing["query_variations"] = sorted(existing_queries | new_queries)
                existing_stories = set(existing.get("relevant_stories", []))
                new_stories = set(intent.get("relevant_stories", []))
                existing["relevant_stories"] = sorted(existing_stories | new_stories)
            else:
                all_intents[intent_id] = intent

    sorted_intents = sorted(all_intents.values(), key=lambda i: i.get("intent_id", ""))
    return {
        "index_type": "intent_mapping",
        "total_intents": len(sorted_intents),
        "intents": sorted_intents,
    }


ASSEMBLERS = {
    "glossary": assemble_glossary,
    "story_summaries": assemble_story_summaries,
    "business_rules": assemble_business_rules,
    "semantic_similarity": assemble_semantic_similarity,
    "cross_story_links": assemble_cross_story_links,
    "intent_mapping": assemble_intent_mapping,
}


def assemble_index(index_name: str, responses: list[BatchResponse]) -> dict[str, Any]:
    """Route to the appropriate assembler for a given index type."""
    assembler = ASSEMBLERS.get(index_name)
    if not assembler:
        raise ValueError(f"Unknown index type: {index_name}. Available: {list(ASSEMBLERS.keys())}")
    return assembler(responses)


def write_index(index_data: dict, output_path: Path) -> None:
    """Write assembled index to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(index_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Wrote {output_path} ({index_data.get('total_terms', index_data.get('total_stories', index_data.get('total_rules', index_data.get('total_groups', index_data.get('total_links', index_data.get('total_intents', '?'))))))} entries)")
