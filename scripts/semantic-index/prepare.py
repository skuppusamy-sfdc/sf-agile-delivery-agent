"""Prepare batch requests from corpus + prompt templates.

Reads story markdown files, chunks them according to config batch_size,
renders prompt templates with story content, and outputs BatchRequest objects.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from adapters.base import BatchRequest

# Default story ID pattern — matches common JIRA formats (PROJ-123, ABC-4567, etc.)
# Override via config.yaml > corpus > story_id_pattern
STORY_ID_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")
SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)
META_RE = re.compile(r"^- \*\*(.+?)\*\*:\s*(.*)$", re.MULTILINE)


def load_corpus(sprints_dir: Path) -> list[dict[str, str]]:
    """Load all per-story markdown files into structured dicts."""
    stories = []
    sprint_dirs = sorted(
        d for d in sprints_dir.iterdir()
        if d.is_dir() and "sprint" in d.name.lower()
    )
    for sprint_dir in sprint_dirs:
        stories_dir = sprint_dir / "stories"
        if not stories_dir.exists():
            continue
        for md_file in sorted(stories_dir.glob("*.md")):
            story = parse_story_md(md_file, sprint_dir.name)
            if story:
                stories.append(story)
    return stories


def parse_story_md(path: Path, sprint_name: str) -> dict[str, str] | None:
    """Parse a single story markdown file into a structured dict."""
    text = path.read_text(encoding="utf-8", errors="replace")

    story_id_match = STORY_ID_RE.search(path.stem)
    if not story_id_match:
        return None

    metadata = {}
    for m in META_RE.finditer(text):
        metadata[m.group(1).strip()] = m.group(2).strip()

    sections = {}
    parts = SECTION_RE.split(text)
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip()] = parts[i + 1].strip()

    title_line = text.split("\n")[0] if text else ""
    summary = ""
    if ":" in title_line:
        summary = title_line.split(":", 1)[1].strip()

    return {
        "id": story_id_match.group(),
        "sprint": sprint_name,
        "summary": summary,
        "type": metadata.get("Type", "Story"),
        "epic": metadata.get("Epic", ""),
        "components": metadata.get("Components", ""),
        "labels": metadata.get("Labels", ""),
        "status": metadata.get("Status", ""),
        "ac": sections.get("Acceptance Criteria", ""),
        "solution": sections.get("Solution", ""),
        "description": sections.get("Description", ""),
    }


def chunk_stories(stories: list[dict], batch_size: int) -> list[list[dict]]:
    """Split stories into chunks of batch_size."""
    return [stories[i:i + batch_size] for i in range(0, len(stories), batch_size)]


def render_prompt(template: str, stories: list[dict], context: dict | None = None) -> str:
    """Render a prompt template with story data injected.

    Template uses {{STORIES}} as placeholder for formatted story content.
    Optional {{CONTEXT}} for additional data (e.g., glossary from prior index).
    """
    story_text = format_stories_for_prompt(stories)
    rendered = template.replace("{{STORIES}}", story_text)

    if context:
        import json
        rendered = rendered.replace("{{CONTEXT}}", json.dumps(context, indent=2))
    else:
        rendered = rendered.replace("{{CONTEXT}}", "")

    return rendered


def _is_defect(story: dict) -> bool:
    """Check if a story is a defect/bug type (content lives in Description, not AC)."""
    story_type = story.get("type", "").lower()
    if story_type in ("bug", "defect"):
        return True
    ac = story.get("ac", "").strip().lower()
    if ac in ("", "as per description", "see description", "refer to description"):
        return True
    return False


def format_stories_for_prompt(stories: list[dict]) -> str:
    """Format stories compactly for inclusion in a prompt.

    For defects/bugs: Description is the primary content field (gets full space).
    For stories: Description provides context alongside AC.
    Description is always included when present.
    """
    lines = []
    for s in stories:
        story_type = s.get("type", "Story")
        lines.append(f"--- STORY: {s['id']} (Sprint: {s['sprint']}, Epic: {s['epic']}, Type: {story_type}) ---")
        lines.append(f"Summary: {s['summary']}")
        if s["components"]:
            lines.append(f"Components: {s['components']}")

        if _is_defect(s):
            if s["description"]:
                lines.append(f"Description:\n{s['description'][:1500]}")
            if s["ac"] and s["ac"].strip().lower() not in (
                "as per description", "see description", "refer to description"
            ):
                lines.append(f"Acceptance Criteria:\n{s['ac'][:800]}")
        else:
            if s["description"]:
                lines.append(f"Description:\n{s['description'][:1000]}")
            if s["ac"]:
                lines.append(f"Acceptance Criteria:\n{s['ac'][:1500]}")

        if s["solution"]:
            lines.append(f"Solution:\n{s['solution'][:1000]}")
        lines.append("")
    return "\n".join(lines)


PROMPT_FILE_MAP = {
    "glossary": "glossary.md",
    "story_summaries": "story-summary.md",
    "business_rules": "business-rules.md",
    "semantic_similarity": "semantic-similarity.md",
    "cross_story_links": "cross-story-links.md",
    "intent_mapping": "intent-mapping.md",
}


def load_prompt_template(prompts_dir: Path, index_name: str) -> str:
    """Load a prompt template markdown file."""
    filename = PROMPT_FILE_MAP.get(index_name, f"{index_name}.md")
    prompt_path = prompts_dir / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def prepare_requests(
    index_name: str,
    stories: list[dict],
    prompts_dir: Path,
    batch_size: int,
    model: str,
    max_tokens: int,
    context: dict | None = None,
) -> list[BatchRequest]:
    """Generate BatchRequest objects for a given index type."""
    template = load_prompt_template(prompts_dir, index_name)
    chunks = chunk_stories(stories, batch_size)

    requests = []
    for i, chunk in enumerate(chunks, 1):
        prompt = render_prompt(template, chunk, context)
        requests.append(BatchRequest(
            custom_id=f"{index_name}-{i:03d}",
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=0.0,
        ))

    return requests
