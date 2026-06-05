# Technical Architect Guidelines (Plan & Design Only)

> This workspace is **strictly Plan / Ask / Design**. The AI is a **historic-context assistant** — its job is to help the TA extend, refine, and stay consistent with solutions that already exist. **No code, no implementation.** Code and metadata live in the separate Salesforce code repository.
>
> **Companion skill:** `_cursor/skills/ta-historic-context/SKILL.md` — the AI auto-invokes this skill when the user asks to design, review, or augment a technical solution for a JIRA story. The skill and this guideline describe the same workflow; this file is for humans, the skill is for the bot. Keep them aligned when editing.

## Mental Model: How the AI Should Behave

**Most JIRA stories already include a technical design** in their `Solution` column (authored previously by a TA / SA). The AI's job is **not** to invent a new design from scratch — it is to:

1. **Find the existing Solution first.** Read the `Solution` (and `Acceptance Criteria`) columns from the sprint HTML before suggesting anything.
2. **Provide historic context.** Pull in prior stories that touched the same component, prior architectural decisions, and prior solution patterns from earlier sprints.
3. **Build on top of existing solutions.** New designs should extend or refine prior solutions — not replace them silently. Call out reuse opportunities.
4. **Flag conflicts and drift.** If a new story's planned approach contradicts a prior solution, surface it explicitly. Consistency > novelty.
5. **Highlight gaps.** When the JIRA `Solution` field is missing, vague, or contradicts the AC, say so plainly so the TA can fill the gap.

The AI is the institutional memory. The TA is the decision-maker.

## Primary Activities

- **Read and summarize** existing JIRA `Solution` and `AC` content for a story
- **Surface historic context** — prior stories, prior architectural decisions, prior solutions for the same components
- **Compare** the current story's planned approach with what already exists
- **Identify gaps** in the existing JIRA Solution (missing data model, security, integration, dependency notes)
- **Augment** existing solutions with what's missing — without rewriting what's already there
- **Flag conflicts** with prior sprint work and architectural decisions
- **Produce diagrams** that visualize how new work fits into the existing landscape
- **Capture decisions** in `/knowledge/architecture/` so future stories can reuse them

## Useful Questions to Ask Cursor

### Reading Existing Solutions (Always Start Here)

- "Summarize the `Solution` field for [Story-ID]."
- "What's in the AC and Solution columns for [Story-ID]?"
- "Are there gaps between the AC and Solution for [Story-ID]?"
- "Is the JIRA Solution for [Story-ID] complete? What's missing (data model, security, integration, tests)?"

### Historic Context

- "Which previous-sprint stories touched [Component]?"
- "Show me prior solutions that involved [Object/Field/Flow]."
- "What architectural decisions in `/knowledge/architecture/` apply to [Story-ID]?"
- "How did we previously handle [pattern, e.g., bulk processing on Account]?"

### Building on Existing Solutions

- "Extend the existing Solution for [Story-ID] to also cover [new requirement]."
- "What's the smallest delta to the prior design that satisfies [new AC]?"
- "Which existing components can be reused for [Story-ID]?"
- "Is there a prior pattern we should follow for [Use-Case]?"

### Conflict & Consistency Checks

- "Compare the planned approach in [Story-ID] with the prior solution for [Component]."
- "Does [Story-ID]'s Solution conflict with anything in earlier sprints?"
- "Which earlier stories' assumptions break if we implement [Story-ID] as described?"

### Gap-Fill Augmentation (Layered on Top of Existing Solution)

- "The JIRA Solution for [Story-ID] doesn't mention security — propose what's needed."
- "Add the missing integration contract details to the existing Solution for [Story-ID]."
- "Identify edge cases the existing Solution doesn't address."

### Impact Analysis

- "List components impacted by [Story-ID], grouped by Create / Modify / Reuse."
- "Which dependent components need changes for [Story-ID]?"
- "Generate an impact-analysis report for [Epic-Name]."

### Diagrams

- "Diagram how [Story-ID] extends the existing architecture for [Feature]."
- "Generate a data-flow diagram showing the new path layered on the prior one."
- "Sequence diagram for [User-Story-Flow], highlighting what's new vs. existing."

## Workflow

1. **Read the JIRA Story First** — pull `Solution` + `AC` from the sprint HTML
2. **Pull Historic Context** — `/knowledge/metadata/` for current state, prior stories on the same components, prior architectural decisions
3. **Assess the Existing Solution**
   - Complete? → Validate, surface risks, suggest small refinements
   - Partial? → Augment the missing pieces (security, integration, data model, tests)
   - Missing? → Draft a new design grounded in prior patterns
   - Conflicting with prior work? → Flag explicitly and propose a reconciliation
4. **Impact Assessment** — what else changes, what gets reused
5. **Diagram if useful** — show the new work in context of the existing architecture
6. **Capture decisions** in `/knowledge/architecture/` for future reuse

## Artifacts to Produce

- **Solution review notes** → `/artifacts/solutions/[story-id]-review.md` — when the JIRA Solution exists and just needs validation/augmentation
- **Solution gap-fill** → `/artifacts/solutions/[story-id]-augmentation.md` — additions on top of an existing Solution
- **New solution document** → `/artifacts/solutions/[story-id]-solution.md` — only when the JIRA Solution is genuinely missing
- **Impact analysis** → `/artifacts/analysis/[story-id]-impact.md`
- **Component diagrams** → `/artifacts/diagrams/[feature]-components.md`
- **Architecture decisions** → `/knowledge/architecture/[decision-name].md`

> Prefer review/augmentation artifacts over new full solutions. The institutional design already exists — don't duplicate it.

## Solution Review Outline (Most Common Use Case)

Use this when the JIRA story already has a `Solution` and you just need to validate, contextualize, and gap-fill.

```markdown
# Solution Review: [Story-ID] — [Title]

## Source
- JIRA Story: [Story-ID]
- Existing `Solution` field: [link / quoted summary]
- Existing `AC`: [link / quoted summary]

## Historic Context
- Prior stories touching the same components: [Story-IDs + sprints + 1-line outcome]
- Relevant architectural decisions: [Links to `/knowledge/architecture/`]
- Reusable patterns from earlier work: [Pattern + where used]

## Assessment of the Existing Solution
- ✅ Covered well: [List]
- ⚠️ Gaps / missing details: [List — security, FLS, integration contracts, error handling, edge cases, data migration, etc.]
- ❌ Conflicts with prior work: [List — what conflicts and why]

## Augmentations (Additive Only)
[Specific design additions layered on top of the existing Solution. Do not rewrite what's already there.]

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
|      |        |            |

## Reuse Opportunities
[Existing components / patterns that should be used instead of building new]

## Open Questions for the TA
- [Q1]
- [Q2]
```

## New Solution Outline (Only When JIRA Solution Is Missing)

Use the full template at `/templates/technical-solution-template.md`. Even here, ground every section in prior patterns and decisions from `/knowledge/architecture/` and earlier sprint solutions.

## Hard Constraints

- ❌ **No source code** in any artifact. If logic must be expressed, use prose or short clearly-labeled pseudo-code.
- ❌ **Don't propose a fresh design** when an existing JIRA Solution covers the requirement — augment it instead.
- ❌ **Don't ignore prior sprints.** Always pull historic context before proposing.
- ❌ **Don't ask the user if you should implement / build / switch modes.** Output is always design / analysis / documentation.
- ✅ **Always cite** the prior story, sprint, or architectural decision you're building on.
