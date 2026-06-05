# Solution Architect Guidelines (Plan & Design Only)

> This workspace is **strictly Plan / Ask / Design**. Focus on cross-sprint consistency, AC validation, and conflict detection. No code, no implementation work happens here.
>
> **Companion skill:** `_cursor/skills/sa-cross-sprint-consistency/SKILL.md` — the AI auto-invokes this skill when the user asks to validate AC, detect conflicts, map dependencies, or assess sprint deliverability. The skill and this guideline describe the same workflow; this file is for humans, the skill is for the bot. Keep them aligned when editing.

## Primary Activities

- Ensure consistency across sprints
- Validate acceptance criteria alignment
- Identify conflicts and dependencies
- Provide confidence assessments on deliverables
- Track architectural decisions

## Useful Questions to Ask Cursor

### Sprint Conflict Detection
- "Analyze Sprint X and Sprint Y stories — identify any conflicts in requirements or planned approach."
- "Compare planned component changes in [Story-ID] with previous sprint changes affecting [Component]."
- "Which stories in previous sprints touched [Object/Component]? Are there conflicts with the current sprint?"

### Acceptance Criteria Validation
- "Review acceptance criteria for [Story-ID] against existing metadata and component state."
- "Which components must be verified to confirm [Story-ID] AC can be met?"
- "Identify gaps or ambiguities in acceptance criteria for Sprint X stories."

### Impact & Dependency Analysis
- "Which previous-sprint stories are affected by changes planned in [Story-ID]?"
- "Generate a dependency map for stories touching [Component]."
- "Identify regression risks for Sprint X deliverables."

## Workflow

1. **Sprint Start** — review all stories vs. previous sprint changes
2. **Mid-Sprint** — monitor for emerging conflicts
3. **Sprint End** — confirm AC are deliverable given current state
4. **Cross-Sprint** — preserve traceability of architectural decisions

## Artifacts to Create

- Sprint conflict reports → `/artifacts/analysis/sprint-X-conflicts.md`
- AC confidence assessments → `/artifacts/analysis/sprint-X-ac-confidence.md`
- Cross-sprint dependency maps → `/artifacts/diagrams/sprint-dependencies.md`
- Architectural decision records → `/knowledge/architecture/[decision].md`

> Output is always analysis, design, or documentation. No code, no metadata XML, no deployment scripts.
