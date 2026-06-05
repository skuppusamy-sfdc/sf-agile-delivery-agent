# Scripts Directory — RAG Index Generation

This directory contains Python scripts that generate the RAG (Retrieval-Augmented Generation) index layer for the Salesforce Knowledge Agent workspace.

---

## 🔥 CRITICAL: After May 19, 2026 Strikethrough Fix

**A critical bug was fixed on May 19, 2026** in `split-sprint-stories.py` that prevented proper filtering of JIRA wiki markup (strikethrough `-text-` and color markup `{color:#hex}`). 

### What Changed

The `_clean()` function now properly filters:
- JIRA wiki strikethrough: `-text-` → removes struck-through deprecated content
- JIRA color markup: `{color:#hex}text{color}` → removes color highlighting

### What You Must Do

**Regenerate ALL per-story markdown files and indexes** to apply the fix:

```bash
# Step 1: Regenerate all per-story markdown files (force overwrite)
python scripts/split-sprint-stories.py --force

# Step 2: Rebuild all aggregate indexes
python scripts/create-ac-index.py
python scripts/create-solution-index.py
python scripts/create-component-story-map.py
python scripts/create-feature-epic-map.py
python scripts/create-dependency-graph.py
python scripts/create-traceability-index.py
```

**Estimated time**: 5-10 minutes for all scripts
**Why this matters**: Without regeneration, 20-36% of stories may contain deprecated/withdrawn requirements marked as active.

---

## 📋 Script Inventory

### Core Processing Scripts

| Script | Purpose | Input | Output | Runtime |
|--------|---------|-------|--------|---------|
| `split-sprint-stories.py` | Split monolithic sprint HTMLs into per-story markdown files | `knowledge/sprints/Sprint N/*.html` | `knowledge/sprints/Sprint N/stories/*.md` | ~30s per sprint |
| `create-ac-index.py` | Generate searchable Acceptance Criteria index | Per-story markdown files | `knowledge/AC-INDEX.md` | ~60s |
| `create-solution-index.py` | Generate searchable Solution index | Per-story markdown files | `knowledge/SOLUTION-INDEX.md` | ~60s |
| `create-component-story-map.py` | Map components to stories | Per-story markdown files | `knowledge/COMPONENT-TO-STORY-MAP.md` | ~45s |
| `create-feature-epic-map.py` | Map features/epics to stories | Per-story markdown files | `knowledge/FEATURE-TO-STORY-MAP.md` | ~30s |
| `create-dependency-graph.py` | Generate story dependency graph | Per-story markdown files | `knowledge/DEPENDENCY-GRAPH.md` | ~30s |
| `create-traceability-index.py` | Create Copado → JIRA traceability index | `knowledge/traceability/*.csv` | `knowledge/TRACEABILITY-INDEX.md` | ~30s |

### Analysis Scripts

| Script | Purpose | Output |
|--------|---------|--------|
| `analyze-corpus.py` | Analyze workspace corpus size, token estimates | Terminal output |
| `analyze-rag-effectiveness.py` | Measure RAG layer compression ratio | Terminal output |
| `analyze-transcripts.py` | Analyze Cursor agent conversation history | Terminal output |
| `catalog-metadata-components.py` | Catalog deployed Salesforce metadata | `knowledge/metadata/CATALOG.md` |

---

## 🚀 Quick Start: First-Time Setup

If you're setting up the workspace for the first time:

```bash
# 1. Generate per-story markdown files from sprint HTMLs
python scripts/split-sprint-stories.py

# 2. Generate all aggregate indexes (run in parallel or sequential)
python scripts/create-ac-index.py
python scripts/create-solution-index.py
python scripts/create-component-story-map.py
python scripts/create-feature-epic-map.py
python scripts/create-dependency-graph.py
python scripts/create-traceability-index.py

# 3. (Optional) Catalog deployed metadata
python scripts/catalog-metadata-components.py
```

**Total time**: ~10-15 minutes for 20 sprints

---

## 🔄 Maintenance: When to Regenerate

### After Adding a New Sprint

```bash
# Regenerate only the new sprint's per-story files
python scripts/split-sprint-stories.py --sprint "Sprint 15"

# Rebuild aggregate indexes (they pull from all sprints)
python scripts/create-ac-index.py
python scripts/create-solution-index.py
python scripts/create-component-story-map.py
python scripts/create-feature-epic-map.py
python scripts/create-dependency-graph.py
```

### After Updating Existing Sprint HTML

```bash
# Force regenerate for the updated sprint
python scripts/split-sprint-stories.py --sprint "Sprint 14" --force

# Rebuild aggregate indexes
python scripts/create-ac-index.py
python scripts/create-solution-index.py
python scripts/create-component-story-map.py
# (run all 6 index scripts)
```

### After Updating Traceability CSV

```bash
# Only need to regenerate the traceability index
python scripts/create-traceability-index.py
```

---

## 📖 Detailed Script Usage

### `split-sprint-stories.py`

**Purpose**: Convert monolithic sprint HTML exports into individual per-story markdown files for efficient RAG retrieval.

**Usage**:
```bash
# Process all sprints
python scripts/split-sprint-stories.py

# Process single sprint
python scripts/split-sprint-stories.py --sprint "Sprint 14"

# Force overwrite existing files
python scripts/split-sprint-stories.py --force

# Combination
python scripts/split-sprint-stories.py --sprint "Sprint 14" --force
```

**Input**: `knowledge/sprints/Sprint N/Your Program [HC] Sprint N.html`
**Output**: `knowledge/sprints/Sprint N/stories/PROJ-1234XXXX.md` (one file per story)
**Compression**: ~40:1 (23 MB HTML → 5.7 MB markdown)

### Index Generation Scripts

All index generation scripts follow the same pattern:

```bash
python scripts/create-[index-name].py
```

No arguments required. They:
1. Read all per-story markdown files from `knowledge/sprints/*/stories/*.md`
2. Extract relevant data
3. Generate a searchable index at `knowledge/[INDEX-NAME].md`
4. Print summary statistics to terminal

---

## 🐛 Troubleshooting

### Error: "No HTML files found"

**Cause**: Script expects files in `knowledge/sprints/Sprint N/` folders
**Fix**: Ensure HTML files are named like `Your Program Sprint 14.html` or `Your Program Sprint 12.html`

### Error: "Import error: BeautifulSoup / pandas"

**Cause**: Missing Python dependencies
**Fix**: Install requirements (TBD: create requirements.txt)

### Per-story files have JIRA markup (`-text-`, `{color:...}`)

**Cause**: You're using the old version of `split-sprint-stories.py` from before May 19, 2026
**Fix**: Pull the latest version and regenerate with `--force`:
```bash
git pull  # or copy latest split-sprint-stories.py
python scripts/split-sprint-stories.py --force
```

### Indexes show "TBD" or are mostly empty

**Cause**: Per-story markdown files don't exist yet
**Fix**: Run `split-sprint-stories.py` first, then regenerate indexes

---

## 📊 Expected Output Sizes

After running all scripts on 20 sprints (1,807 stories):

| Output | Size | Stories/Records |
|--------|------|-----------------|
| Per-story markdown files | ~5.7 MB | 1,807 files |
| AC-INDEX.md | ~485 KB | 1,055 stories with AC |
| SOLUTION-INDEX.md | ~501 KB | ~900 stories with Solution |
| COMPONENT-TO-STORY-MAP.md | ~151 KB | 1,830 mappings |
| FEATURE-TO-STORY-MAP.md | ~329 KB | ~800 mappings |
| DEPENDENCY-GRAPH.md | ~100 KB | ~400 dependencies |
| TRACEABILITY-INDEX.md | ~47 KB | 80,517 CSV rows compressed |
| **Total RAG layer** | **~6.7 MB** | **56:1 compression vs raw** |

---

## 🔧 Development Notes

### Shared Parser Pattern

Five scripts (`split-sprint-stories.py`, `create-ac-index.py`, `create-solution-index.py`, `create-component-story-map.py`, `parse-sprint-html.py`) duplicate similar HTML parsing logic. 

**Future improvement**: Extract shared parser into `scripts/lib/parser.py` to reduce duplication and improve maintainability.

### Strikethrough Filter Evolution

- **Before May 19, 2026**: No JIRA markup filtering; deprecated content leaked through
- **May 19, 2026**: Added regex filters for `-text-` and `{color:...}` in `_clean()` function
- **Future**: Consider adding filter for other JIRA wiki markup (`{panel}`, `{code}`, etc.) if they appear

---

## 📚 Related Documentation

- **UPDATES-SUMMARY.md** — Changelog including the May 19, 2026 strikethrough fix
- **POPULATE-INDEX-INSTRUCTIONS.md** — How to populate the SPRINT-INDEX.md quick-reference file
- **BUILD-GUIDE.md** — Complete workspace setup guide (Phase 5-6 cover script execution)
- **.cursor/rules/html-story-parsing.md** — Rule defining how AI should interpret JIRA markup

---

**Last Updated**: May 19, 2026 (Added strikethrough fix instructions)
