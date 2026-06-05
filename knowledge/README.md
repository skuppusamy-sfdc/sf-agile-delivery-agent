# /knowledge — project content lives here

This folder holds the **content** of your program: sprint exports, traceability, ADRs, and metadata snapshots.

## Subfolders

| Folder | What goes in | Generated? |
|---|---|---|
| `sprints/` | JIRA HTML exports (`Sprint N/*.html`) + auto-generated per-story markdown (`Sprint N/stories/STORY-ID.md`) | input + generated |
| `metadata/` | per-component documentation using `templates/metadata-documentation-template.md` — **(v2) source of truth for current state** (see `_cursor/rules/metadata-is-source-of-truth.mdc`) | input |
| `traceability/` | per-epic traceability matrices | input |
| `architecture/` | ADRs (`ADR-NNN-*.md`) | input |
| `components/` | deeper write-ups when a single component warrants more than a metadata doc | input |

## Generated index files (do not hand-edit)

The `scripts/` rebuild these on demand. They're listed in `.gitignore` because they're regenerable.

- `AC-INDEX.md` — every AC across every sprint
- `SOLUTION-INDEX.md` — every Solution column across every sprint
- `COMPONENT-TO-STORY-MAP.md` — components → stories that touch them
- `FEATURE-TO-STORY-MAP.md` — feature/epic → child stories
- `DEPENDENCY-GRAPH.md` — story → blockers / blocks
- `TRACEABILITY-INDEX.md` — full matrix
- `sprints/SPRINT-INDEX.md` — story directory across all sprints
- `sprints/MASTER-STORY-INDEX.md` — flat story list
- `metadata/COMPONENT-CATALOG.md` — snapshot of `metadata_repo` components

## How to regenerate

```bash
python scripts/split-sprint-stories.py --force
python scripts/parse-sprint-html.py
for s in scripts/create-*.py; do python "$s"; done
python scripts/catalog-metadata-components.py
```
