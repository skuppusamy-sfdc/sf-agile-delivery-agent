#!/usr/bin/env python3
"""
parse-sprint-html.py

Parse JIRA HTML exports under knowledge/sprints/ and produce:
  - knowledge/sprints/MASTER-STORY-INDEX.md (flat list of every story)
  - knowledge/sprints/SPRINT-INDEX.md       (per-sprint headlines + counts)

Reads project-specific config from workspace.config.yaml (story_id pattern, etc.).
Column detection is heuristic; it relies on JIRA's standard `data-id`/class hints
on `<th>`/`<td>` elements. If your export uses non-standard column names, edit
COLUMN_HINTS below.

Usage:
    python scripts/parse-sprint-html.py
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List

import _config as cfg


# ---------------------------------------------------------------------------
# Column detection — extend if your JIRA export uses different headers/classes
# ---------------------------------------------------------------------------
COLUMN_HINTS = {
    "issue_key":     ("issuekey",),
    "summary":       ("summary",),
    "status":        ("status",),                 # excludes "statuscategory"
    "components":    ("components", "component"),
    "ac":            ("acceptance", "ac", "customfield_acceptance"),
    "solution":      ("solution", "approach", "customfield_solution"),
    "story_points":  ("storypoints", "story_points", "customfield_storypoints"),
    "sprint":        ("sprint",),
    "assignee":      ("assignee",),
    "priority":      ("priority",),
}


# ---------------------------------------------------------------------------
# HTML parser
# ---------------------------------------------------------------------------
class JiraHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_header = False
        self.in_body = False
        self.in_row = False
        self.in_cell = False
        self.current_row: List[Dict[str, str]] = []
        self.current_cell = ""
        self.current_cell_class = ""
        self.headers: List[Dict[str, str]] = []
        self.stories: List[List[Dict[str, str]]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table" and (a.get("id") == "issuetable" or "issue" in (a.get("class") or "")):
            self.in_table = True
        elif self.in_table and tag == "thead":
            self.in_header = True
        elif self.in_table and tag == "tbody":
            self.in_body = True
        elif self.in_row and tag in ("th", "td"):
            self.in_cell = True
            self.current_cell = ""
            self.current_cell_class = (a.get("class", "") + " " + a.get("data-id", "")).lower()
        elif (self.in_header or self.in_body) and tag == "tr":
            self.in_row = True
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == "table" and self.in_table:
            self.in_table = False
        elif tag == "thead":
            self.in_header = False
        elif tag == "tbody":
            self.in_body = False
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.in_header and self.current_row:
                self.headers = self.current_row
            elif self.in_body and self.current_row:
                self.stories.append(self.current_row[:])
        elif tag in ("th", "td") and self.in_cell:
            self.in_cell = False
            self.current_row.append(
                {"class": self.current_cell_class, "content": self.current_cell.strip()}
            )

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------
def _matches(cell_class: str, hints: tuple[str, ...]) -> bool:
    if any(h in cell_class for h in hints):
        # exclude statuscategory false-positive for "status"
        if "statuscategory" in cell_class and "status" in hints:
            return False
        return True
    return False


def _extract_story(cells: List[Dict[str, str]]) -> Dict[str, str]:
    story: Dict[str, str] = {}
    for cell in cells:
        cls = cell["class"]
        content = cell["content"]
        for field, hints in COLUMN_HINTS.items():
            if _matches(cls, hints) and field not in story:
                if field == "issue_key":
                    m = cfg.STORY_ID_PATTERN_LOOSE.search(content)
                    if m:
                        story[field] = m.group(0)
                else:
                    story[field] = content
                break
    return story


def parse_sprint_html(html_file: Path, sprint_name: str) -> List[Dict[str, str]]:
    print(f"  Parsing {html_file.name}…")
    parser = JiraHTMLParser()
    parser.feed(html_file.read_text(encoding="utf-8", errors="replace"))
    stories: List[Dict[str, str]] = []
    for cells in parser.stories:
        s = _extract_story(cells)
        if "issue_key" in s:
            s["sprint"] = sprint_name
            stories.append(s)
    print(f"    → {len(stories)} stories")
    return stories


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------
def _truncate(text: str, n: int) -> str:
    text = (text or "").replace("
", " ").replace("|", "\|")
    return text if len(text) <= n else text[: n - 1] + "…"


def render_master_index(stories: List[Dict[str, str]]) -> str:
    lines = [
        f"# Master Story Index — {cfg.PROJECT_NAME}",
        "",
        "_Auto-generated by `scripts/parse-sprint-html.py`. Do not hand-edit._",
        "",
        f"**Total stories**: {len(stories)}",
        "",
        "## All stories",
        "",
        "| Story | Sprint | Summary | Status | Components | Has AC | Has Solution |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in sorted(stories, key=lambda x: (x.get("sprint", ""), x.get("issue_key", ""))):
        lines.append(
            "| {key} | {sprint} | {summary} | {status} | {components} | {ac} | {sol} |".format(
                key=s.get("issue_key", ""),
                sprint=s.get("sprint", ""),
                summary=_truncate(s.get("summary", ""), 60),
                status=_truncate(s.get("status", ""), 20),
                components=_truncate(s.get("components", ""), 40),
                ac="Yes" if s.get("ac", "").strip() else "No",
                sol="Yes" if s.get("solution", "").strip() else "No",
            )
        )
    return "
".join(lines) + "
"


def render_sprint_index(stories: List[Dict[str, str]]) -> str:
    by_sprint: Dict[str, List[Dict[str, str]]] = {}
    for s in stories:
        by_sprint.setdefault(s.get("sprint", "Unknown"), []).append(s)

    lines = [
        f"# Sprint Index — {cfg.PROJECT_NAME}",
        "",
        "_Auto-generated by `scripts/parse-sprint-html.py`. Do not hand-edit._",
        "",
        "## Sprint summary",
        "",
        "| Sprint | Stories | Done | In Progress | Other |",
        "|---|---:|---:|---:|---:|",
    ]
    for sprint in sorted(by_sprint):
        items = by_sprint[sprint]
        done = sum(1 for x in items if x.get("status", "").lower() == "done")
        ip = sum(1 for x in items if "progress" in x.get("status", "").lower())
        other = len(items) - done - ip
        lines.append(f"| {sprint} | {len(items)} | {done} | {ip} | {other} |")

    lines += ["", "## Per-sprint detail", ""]
    for sprint in sorted(by_sprint):
        lines.append(f"### {sprint}")
        lines.append("")
        lines.append("| Story | Summary | Status | Components |")
        lines.append("|---|---|---|---|")
        for s in sorted(by_sprint[sprint], key=lambda x: x.get("issue_key", "")):
            lines.append(
                "| {k} | {sum} | {st} | {c} |".format(
                    k=s.get("issue_key", ""),
                    sum=_truncate(s.get("summary", ""), 70),
                    st=_truncate(s.get("status", ""), 20),
                    c=_truncate(s.get("components", ""), 40),
                )
            )
        lines.append("")
    return "
".join(lines) + "
"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    cfg.banner("parse-sprint-html")
    if not cfg.SPRINTS_DIR.exists():
        print(f"No sprints directory at {cfg.SPRINTS_DIR}. Nothing to do.")
        return 0

    all_stories: List[Dict[str, str]] = []
    for sprint_dir in cfg.find_sprint_dirs():
        for html_file in sorted(sprint_dir.glob(cfg.CONFIG["sprints"]["html_export_pattern"])):
            try:
                all_stories.extend(parse_sprint_html(html_file, sprint_dir.name))
            except Exception as e:
                print(f"  ERROR parsing {html_file}: {e}")

    if not all_stories:
        print("No stories found. Drop JIRA HTML exports under knowledge/sprints/Sprint N/ and rerun.")
        return 0

    (cfg.SPRINTS_DIR / "MASTER-STORY-INDEX.md").write_text(
        render_master_index(all_stories), encoding="utf-8"
    )
    (cfg.SPRINTS_DIR / "SPRINT-INDEX.md").write_text(
        render_sprint_index(all_stories), encoding="utf-8"
    )
    print(f"
✓ Wrote MASTER-STORY-INDEX.md and SPRINT-INDEX.md ({len(all_stories)} stories).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
