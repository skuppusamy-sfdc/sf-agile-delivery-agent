"""
Shared configuration loader for all knowledge-workspace scripts.

Reads `workspace.config.yaml` from the workspace root. If PyYAML is not
installed, a tiny fallback parser handles the simple subset we need.

All scripts in this folder import CONFIG from here. No script should
hard-code paths, regex patterns, or project-specific values.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULTS: Dict[str, Any] = {
    "project": {
        "name": "Salesforce Program",
        "short_code": "SF",
        "description": "",
    },
    "story_id": {
        "pattern": r"^[A-Z]+-\d+$",
        "example": "PROJ-123",
        "jira_base_url": "",
        "copado_base_url": "",
    },
    "metadata_repo": {
        "local_path": "",
        "remote_url": "",
        "default_branch": "main",
        "metadata_root": "force-app/main/default",
    },
    "sprints": {
        "cadence_weeks": 2,
        "start_date": "",
        "html_export_pattern": "*.html",
        "folder_pattern": "Sprint {n}",
    },
    "indexing": {
        "refresh_on_sprint_drop": True,
        "prefer_index_over_html": True,
        "large_file_threshold_lines": 5000,
    },
}


# ---------------------------------------------------------------------------
# Workspace root resolution
# ---------------------------------------------------------------------------
def workspace_root() -> Path:
    """Return the workspace root (the directory containing workspace.config.yaml).

    Walks up from this file's location.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "workspace.config.yaml").exists():
            return candidate
        if (candidate / "workspace.config.example.yaml").exists():
            return candidate
    return here.parent


# ---------------------------------------------------------------------------
# YAML loading (with fallback for installs without PyYAML)
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        return _tiny_yaml_parse(path)


_INLINE_COMMENT = re.compile(r'(?<!\\)\s+#.*$')


def _strip_inline_comment(value: str) -> str:
    """Strip a trailing `# comment` only if it isn't inside quotes.

    Handles the common case: `key: "val"   # note` → `"val"`.
    """
    in_quote: str = ""
    for i, ch in enumerate(value):
        if ch in ('"', "'"):
            if not in_quote:
                in_quote = ch
            elif in_quote == ch:
                in_quote = ""
        elif ch == "#" and not in_quote and (i == 0 or value[i - 1].isspace()):
            return value[:i].rstrip()
    return value


def _coerce_scalar(value: str) -> Any:
    """Decode a scalar: strip comments, strip quotes (with escape handling),
    coerce booleans / ints. Numbers in quoted strings stay strings.
    """
    value = _strip_inline_comment(value).strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        inner = value[1:-1]
        # Handle the two backslash escapes our config example uses
        return inner.replace("\\\\", "\\").replace('\\"', '"')
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return ""
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def _tiny_yaml_parse(path: Path) -> Dict[str, Any]:
    """Minimal YAML subset parser: 2-space indent, key:value, lists with -.

    Sufficient for workspace.config.yaml. Install PyYAML for anything richer.
    """
    result: Dict[str, Any] = {}
    stack: list = [(0, result)]

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            content = line.strip()

            while stack and indent < stack[-1][0]:
                stack.pop()
            parent = stack[-1][1] if stack else result

            if content.startswith("- "):
                value = _coerce_scalar(content[2:])
                if isinstance(parent, list):
                    parent.append(value)
                continue

            if ":" in content:
                key, _, value = content.partition(":")
                key = key.strip()
                value = value.strip()
                if value == "" or value.startswith("#"):
                    new_container: Any = {}
                    if isinstance(parent, dict):
                        parent[key] = new_container
                    stack.append((indent + 2, new_container))
                else:
                    if isinstance(parent, dict):
                        parent[key] = _coerce_scalar(value)
    return result


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
ROOT = workspace_root()

_config_path = ROOT / "workspace.config.yaml"
if not _config_path.exists():
    _config_path = ROOT / "workspace.config.example.yaml"

_user_config = _load_yaml(_config_path) if _config_path.exists() else {}
CONFIG: Dict[str, Any] = _deep_merge(DEFAULTS, _user_config)

STORY_ID_PATTERN = re.compile(CONFIG["story_id"]["pattern"])
STORY_ID_PATTERN_LOOSE = re.compile(
    CONFIG["story_id"]["pattern"].lstrip("^").rstrip("$")
)
PROJECT_NAME: str = CONFIG["project"]["name"]
SPRINTS_DIR = ROOT / "knowledge" / "sprints"
KNOWLEDGE_DIR = ROOT / "knowledge"
METADATA_DIR = KNOWLEDGE_DIR / "metadata"
ARTIFACTS_DIR = ROOT / "artifacts"
METADATA_REPO_PATH = (
    Path(CONFIG["metadata_repo"]["local_path"]).expanduser()
    if CONFIG["metadata_repo"]["local_path"]
    else None
)
METADATA_REPO_ROOT = (
    METADATA_REPO_PATH / CONFIG["metadata_repo"]["metadata_root"]
    if METADATA_REPO_PATH
    else None
)


def banner(script_name: str) -> None:
    """Print a small header so users know which script ran."""
    print(f"\n=== {script_name} — {PROJECT_NAME} ===")
    print(f"Workspace: {ROOT}")
    if not (ROOT / "workspace.config.yaml").exists():
        print(
            "WARNING: workspace.config.yaml not found; using example defaults. "
            "Copy workspace.config.example.yaml → workspace.config.yaml.",
            file=sys.stderr,
        )


def find_sprint_dirs() -> list[Path]:
    """Return sprint subdirectories under knowledge/sprints/, sorted."""
    if not SPRINTS_DIR.exists():
        return []
    pattern_word = CONFIG["sprints"]["folder_pattern"].split("{")[0].strip()
    return sorted(
        d
        for d in SPRINTS_DIR.iterdir()
        if d.is_dir() and (not pattern_word or pattern_word.lower() in d.name.lower())
    )
