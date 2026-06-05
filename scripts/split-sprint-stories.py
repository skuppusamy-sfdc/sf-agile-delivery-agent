#!/usr/bin/env python3
"""
Sprint Story Splitter — Split monolithic JIRA HTML exports into per-story markdown files.

Reads each sprint HTML file and writes one .md file per story to a `stories/` subdirectory.
This dramatically improves RAG retrieval by letting the AI fetch a single 2-30KB story
instead of parsing a 1-4.5MB sprint HTML.

Usage:
    python split-sprint-stories.py                      # all sprints
    python split-sprint-stories.py --sprint "Sprint 14"  # single sprint
    python split-sprint-stories.py --force               # overwrite existing
"""

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

STORY_ID_RE = re.compile(r"PR\d+-\d+")

FIELD_MAP = {
    "issuekey":            "issue_key",
    "summary":             "summary",
    "status":              "status",
    "statusCategory":      "status_category",
    "issuetype":           "issue_type",
    "priority":            "priority",
    "assignee":            "assignee",
    "reporter":            "reporter",
    "creator":             "creator",
    "components":          "components",
    "parent":              "epic",
    "labels":              "labels",
    "resolution":          "resolution",
    "description":         "description",
    "customfield_XXXXX":   "acceptance_criteria",
    "customfield_YYYYY":   "solution",
    "customfield_ZZZZZ":   "build_components",
    "customfield_10035":   "deployment_instructions",
    "customfield_10036":   "epic_theme",
    "customfield_10047":   "story_points",
    "customfield_10020":   "sprint_name",
    "customfield_10300":   "root_cause",
    "customfield_10301":   "root_cause_type",
    "customfield_10038":   "environment",
    "issuelinks":          "linked_issues",
    "subtasks":            "subtasks",
    "created":             "created",
    "updated":             "updated",
    "resolutiondate":      "resolved",
}


class StoryHTMLParser(HTMLParser):
    """Parse JIRA HTML table exports, preserving full content with line breaks."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_header = False
        self.in_body = False
        self.in_row = False
        self.in_cell = False

        self.current_row: list[dict] = []
        self.current_cell = ""
        self.current_cell_class = ""
        self.current_issue_key = ""
        self.stories: list[list[dict]] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "table" and attrs_dict.get("id") == "issuetable":
            self.in_table = True
        elif self.in_table and tag == "thead":
            self.in_header = True
        elif self.in_table and tag == "tbody":
            self.in_body = True
        elif self.in_body and tag == "tr" and "issuerow" in attrs_dict.get("class", ""):
            self.in_row = True
            self.current_row = []
            self.current_issue_key = attrs_dict.get("data-issuekey", "")
        elif self.in_row and tag == "td":
            self.in_cell = True
            self.current_cell = ""
            self.current_cell_class = attrs_dict.get("class", "").strip()
        elif self.in_cell and tag in ("br", "p"):
            self.current_cell += "\n"
        elif self.in_cell and tag == "li":
            self.current_cell += "\n- "

    def handle_endtag(self, tag):
        if tag == "table" and self.in_table:
            self.in_table = False
        elif tag == "thead":
            self.in_header = False
        elif tag == "tbody":
            self.in_body = False
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.current_row:
                self.stories.append(self.current_row[:])
        elif tag == "td" and self.in_cell:
            self.in_cell = False
            self.current_row.append({
                "class": self.current_cell_class,
                "content": self.current_cell.strip(),
            })

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def handle_entityref(self, name):
        if self.in_cell:
            self.current_cell += html.unescape(f"&{name};")

    def handle_charref(self, name):
        if self.in_cell:
            self.current_cell += html.unescape(f"&#{name};")


def _clean(text: str) -> str:
    """Collapse excessive blank lines, strip JIRA wiki markup, and trim whitespace."""
    text = text.strip()
    
    # Filter JIRA wiki strikethrough: -text-
    # Matches text surrounded by dashes, but not list bullets (- at start of line)
    text = re.sub(r'(?<!^)(?<!\n)-([^-\n]+)-', r'\1', text, flags=re.MULTILINE)
    
    # Filter JIRA color markup: {color:#hex}text{color}
    text = re.sub(r'\{color:[^}]+\}', '', text)  # Opening tags with hex
    text = re.sub(r'\{color\}', '', text)  # Closing tags
    
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text


def _extract_story(cells: list[dict], sprint_folder: str) -> dict[str, str]:
    """Map raw cell data to a clean story dict."""
    story: dict[str, str] = {"sprint_folder": sprint_folder}
    seen_status = False

    for cell in cells:
        cls = cell["class"]
        content = cell["content"]

        if cls == "status" and not seen_status:
            seen_status = True
            story["status"] = content
            continue
        if cls == "statusCategory":
            continue

        field = None
        for css_key, field_name in FIELD_MAP.items():
            if css_key == cls:
                field = field_name
                break

        if field and field not in story:
            if field == "issue_key":
                m = STORY_ID_RE.search(content)
                story[field] = m.group() if m else content.strip()
            else:
                story[field] = content

    return story


def _jira_wiki_to_md(text: str) -> str:
    """Minimal Jira-wiki-markup to markdown conversion."""
    text = re.sub(r"^h([1-6])\.\s*", lambda m: "#" * int(m.group(1)) + " ", text, flags=re.MULTILINE)
    text = re.sub(r"\*([^*\n]+)\*", r"**\1**", text)
    text = re.sub(r"\{\\{([^}]+)\\}\}", r"`\1`", text)
    text = re.sub(r"\{\{([^}]+)\}\}", r"`\1`", text)
    text = re.sub(r"^\*\s", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s", "1. ", text, flags=re.MULTILINE)
    return text


def story_to_markdown(story: dict[str, str]) -> str:
    """Render a story dict as a markdown document."""
    key = story.get("issue_key", "UNKNOWN")
    summary = story.get("summary", "No summary")
    lines = [f"# {key}: {summary}", ""]

    meta_fields = [
        ("Sprint",       story.get("sprint_name") or story.get("sprint_folder", "")),
        ("Status",       story.get("status", "")),
        ("Type",         story.get("issue_type", "")),
        ("Priority",     story.get("priority", "")),
        ("Resolution",   story.get("resolution", "")),
        ("Assignee",     story.get("assignee", "")),
        ("Reporter",     story.get("reporter", "")),
        ("Components",   story.get("components", "")),
        ("Epic",         story.get("epic", "") or story.get("epic_theme", "")),
        ("Story Points", story.get("story_points", "")),
        ("Labels",       story.get("labels", "")),
        ("Environment",  story.get("environment", "")),
        ("Created",      story.get("created", "")),
        ("Resolved",     story.get("resolved", "")),
        ("Updated",      story.get("updated", "")),
    ]
    for label, value in meta_fields:
        value = value.strip()
        if value and value != "&nbsp;":
            lines.append(f"- **{label}**: {value}")
    lines.append("")

    rich_sections = [
        ("Description",              "description"),
        ("Acceptance Criteria",      "acceptance_criteria"),
        ("Solution",                 "solution"),
        ("Build Components",         "build_components"),
        ("Deployment Instructions",  "deployment_instructions"),
        ("Root Cause",               "root_cause"),
        ("Root Cause Type",          "root_cause_type"),
    ]
    for heading, field in rich_sections:
        content = _clean(story.get(field, ""))
        if content and content != "&nbsp;":
            content = _jira_wiki_to_md(content)
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(content)
            lines.append("")

    link_sections = [
        ("Linked Issues", "linked_issues"),
        ("Sub-tasks",     "subtasks"),
    ]
    for heading, field in link_sections:
        raw = story.get(field, "").strip()
        if raw:
            ids = STORY_ID_RE.findall(raw)
            if ids:
                lines.append(f"## {heading}")
                lines.append("")
                for sid in ids:
                    lines.append(f"- {sid}")
                lines.append("")

    return "\n".join(lines) + "\n"


def process_sprint(sprint_dir: Path, force: bool = False) -> int:
    """Split one sprint HTML into per-story markdown files. Returns story count."""
    html_files = list(sprint_dir.glob("*.html"))
    if not html_files:
        return 0

    stories_dir = sprint_dir / "stories"

    if stories_dir.exists() and not force:
        existing = list(stories_dir.glob("*.md"))
        if existing:
            print(f"  Skipping {sprint_dir.name} — {len(existing)} story files exist (use --force to overwrite)")
            return 0

    html_file = html_files[0]
    print(f"  Parsing {html_file.name} ...")

    with open(html_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    parser = StoryHTMLParser()
    parser.feed(content)

    if not parser.stories:
        print(f"  WARNING: No stories found in {html_file.name}")
        return 0

    stories_dir.mkdir(exist_ok=True)
    count = 0

    for cells in parser.stories:
        story = _extract_story(cells, sprint_dir.name)
        issue_key = story.get("issue_key")
        if not issue_key:
            continue

        md_content = story_to_markdown(story)
        out_path = stories_dir / f"{issue_key}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        count += 1

    print(f"  Wrote {count} story files to {stories_dir}/")
    return count


def main():
    parser = argparse.ArgumentParser(description="Split JIRA sprint HTML exports into per-story markdown files")
    parser.add_argument("--sprint", help="Process only this sprint folder (e.g. 'Sprint 14')")
    parser.add_argument("--force", action="store_true", help="Overwrite existing story files")
    args = parser.parse_args()

    base_path = Path(__file__).resolve().parent.parent / "knowledge" / "sprints"
    if not base_path.exists():
        print(f"ERROR: Sprint directory not found: {base_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Sprint Story Splitter ===")
    print(f"Sprints dir: {base_path}")

    if args.sprint:
        target = base_path / args.sprint
        if not target.exists():
            print(f"ERROR: Sprint folder not found: {target}", file=sys.stderr)
            sys.exit(1)
        sprint_dirs = [target]
    else:
        sprint_dirs = sorted(
            d for d in base_path.iterdir()
            if d.is_dir() and "sprint" in d.name.lower()
        )

    total = 0
    for sprint_dir in sprint_dirs:
        total += process_sprint(sprint_dir, force=args.force)

    print(f"\nDone. {total} story files written across {len(sprint_dirs)} sprints.")


if __name__ == "__main__":
    main()
