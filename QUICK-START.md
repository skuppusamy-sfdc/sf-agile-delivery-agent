# Quick-Start Recipes

Copy-paste recipes for the most common tasks. Each recipe is ~30 seconds.

> **First-time user?** Read `START-HERE.md` first — it walks through the one-time setup (copy → rename `_cursor` → create `workspace.config.yaml` → drop your first sprint) and explains *why* each step exists. The recipes below assume that's done.

---

## Sprint operations

### Onboard a new sprint

> **Export from JIRA as HTML** (Issues → JQL → Export → HTML). Not CSV, not pasted text. HTML preserves strikethrough on superseded AC/Solution content; CSV flattens it. See `_cursor/rules/jira-html-parsing.mdc`.

```bash
SPRINT_NUM=4
mkdir -p "knowledge/sprints/Sprint $SPRINT_NUM"
cp ~/Downloads/sprint${SPRINT_NUM}-export.html "knowledge/sprints/Sprint $SPRINT_NUM/"
python scripts/split-sprint-stories.py --sprint "Sprint $SPRINT_NUM"
python scripts/parse-sprint-html.py
python scripts/create-ac-index.py
python scripts/create-solution-index.py
python scripts/create-component-story-map.py
python scripts/create-dependency-graph.py
```

### Refresh **all** indexes after multiple sprints land
```bash
python scripts/split-sprint-stories.py --force
for s in scripts/create-*.py; do python "$s"; done
```

---

## v3 — RAG analysis (measure and improve)

### Profile your knowledge base
```bash
python scripts/analyze-corpus.py
# → artifacts/analysis/corpus-profile.md
#   Coverage, density, quality scores, topic clusters, component frequency
```

### Analyze what users are asking
```bash
python scripts/analyze-transcripts.py
# → artifacts/analysis/query-patterns.md
#   Intent classification, most-queried stories/components, tool usage patterns
```

### Analyze token spend and cost
```bash
python scripts/import-usage-csv.py ~/Downloads/team-usage-events-*.csv
# → artifacts/analysis/usage-trends.md
#   Per-model costs, cache hit rates, daily trends, cost outliers
```

### Score RAG effectiveness end-to-end
```bash
python scripts/analyze-rag-effectiveness.py
# → artifacts/analysis/rag-effectiveness-report.md
#   Retrieval quality scores, knowledge gaps, component coverage analysis
```

> Run these periodically (e.g., after each sprint) to track improvement over time. All scripts are zero-dependency (Python stdlib only) and output to the shared workspace.

---

## v2 — Skill-driven story workflows

The 4 role skills auto-fire based on the question phrasing. You don't need to invoke them explicitly.

| Role | Sample prompt | Skill that fires | Output |
|------|---------------|------------------|--------|
| TA | *"Review the technical solution for STORY-205"* | `ta-historic-context` | Solution review in `artifacts/solutions/STORY-205-review.md` |
| TA | *"Is the JIRA Solution for STORY-205 complete?"* | `ta-historic-context` | Gap analysis with augmentations |
| SA | *"Find conflicts in Sprint 7"* | `sa-cross-sprint-consistency` | Conflict report in `artifacts/analysis/sprint-7-conflicts.md` |
| SA | *"Validate AC for STORY-205"* | `sa-cross-sprint-consistency` | AC confidence assessment |
| Dev | *"What should I be careful about implementing STORY-205?"* | `dev-story-prep` | Dev prep brief in `artifacts/analysis/STORY-205-dev-prep.md` |
| Dev | *"Unit-test scenarios for STORY-205"* | `dev-story-prep` | Scenario doc in `artifacts/test-plans/STORY-205-unit-scenarios.md` |
| QA | *"Test scenarios for STORY-205"* | `qa-test-scenarios` | Scenario doc in `artifacts/test-plans/STORY-205-scenarios.md` |
| QA | *"Regression scope for Sprint 7"* | `qa-test-scenarios` | Regression scope doc |

---

## Story queries (in Cursor)

| Question | Why it's cheap |
|---|---|
| *"Show all stories that touch the Account object"* | reads `COMPONENT-TO-STORY-MAP.md` |
| *"What ACs reference 'multi-currency'?"* | greps `AC-INDEX.md` |
| *"Which stories depend on STORY-101?"* | reads `DEPENDENCY-GRAPH.md` |
| *"Summarize Sprint 3"* | reads `SPRINT-INDEX.md` |
| *"What's the solution approach for STORY-205?"* | greps `SOLUTION-INDEX.md` |

---

## Authoring artifacts manually (when not using skills)

### New technical solution
```bash
STORY=STORY-205; SLUG=order-cancellation-flow
cp templates/technical-solution-template.md \
   "artifacts/solutions/${STORY}-${SLUG}.md"
```

### New traceability matrix (per epic)
```bash
EPIC=EPIC-12
cp templates/traceability-matrix-template.md \
   "knowledge/traceability/${EPIC}-traceability.md"
```

### New architecture decision record (ADR)
```bash
N=$(ls knowledge/architecture/ 2>/dev/null | grep -c '^ADR-' || echo 0); N=$((N+1))
cat > "knowledge/architecture/ADR-$(printf '%03d' $N)-title.md" <<'EOF'
# ADR-XXX: Title

**Status**: Proposed | Accepted | Superseded
**Date**: YYYY-MM-DD
**Deciders**: ...

## Context
## Decision
## Consequences
EOF
```

### Document a metadata component (source of truth)
```bash
NAME=Account; TYPE=object
mkdir -p "knowledge/metadata/${TYPE}s"
cp templates/metadata-documentation-template.md \
   "knowledge/metadata/${TYPE}s/${NAME}.md"
```

> Reminder: `/knowledge/metadata/` is the **source of truth for current state**. Keep it accurate after each deployment.

---

## Cataloging the metadata repo

Make sure `workspace.config.yaml > metadata_repo.local_path` is correct, then:

```bash
python scripts/catalog-metadata-components.py
# → writes knowledge/metadata/COMPONENT-CATALOG.md
```

---

## Cursor mode cheat-sheet (v2)

| Mode | Use |
|---|---|
| **Ask** | Lookup, summarize, find conflicts. Read-only, cheap. |
| **Plan** | Design a solution, break down a story, evaluate trade-offs. Read-only, more thorough. |
| **Agent** | Intentionally minimal use in this workspace. The rules block code generation in **all** modes. Only use Agent mode for writing analysis/design markdown files. |

The AI rules `_cursor/rules/plan-and-ask-only.mdc` and `_cursor/rules/no-code-development.md` block code generation in all modes.
