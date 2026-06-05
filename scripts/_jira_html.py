"""
Shared JIRA HTML extraction helpers used by multiple scripts.

Avoids duplicating the parser across create-ac-index, create-solution-index,
create-component-story-map, etc.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import _config as cfg

# Re-use the parser & extractor from the main parse script
import importlib.util as _ilu

_parse_path = Path(__file__).resolve().parent / "parse-sprint-html.py"
_spec = _ilu.spec_from_file_location("_parse_sprint_html", _parse_path)
_mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

JiraHTMLParser = _mod.JiraHTMLParser
parse_sprint_html = _mod.parse_sprint_html


def all_stories() -> List[Dict[str, str]]:
    """Walk all sprint dirs and return a flat list of stories."""
    out: List[Dict[str, str]] = []
    for sprint_dir in cfg.find_sprint_dirs():
        for html_file in sorted(sprint_dir.glob(cfg.CONFIG["sprints"]["html_export_pattern"])):
            try:
                out.extend(parse_sprint_html(html_file, sprint_dir.name))
            except Exception as e:
                print(f"  ERROR parsing {html_file}: {e}")
    return out
