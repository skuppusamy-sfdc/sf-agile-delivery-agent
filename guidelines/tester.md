# Tester Guidelines (Plan & Design Only)

> This workspace is **strictly Plan / Ask / Design**. Produce test **scenarios**, **plans**, and **traceability** — not executable test code. Apex test classes and automation scripts live in the separate code repository.
>
> **Companion skill:** `_cursor/skills/qa-test-scenarios/SKILL.md` — the AI auto-invokes this skill when the user asks to plan tests, generate scenarios, validate AC coverage, identify edge cases, or plan regression. The skill and this guideline describe the same workflow; this file is for humans, the skill is for the bot. Keep them aligned when editing.

## Primary Activities

- Plan comprehensive test scenarios
- Validate AC coverage
- Identify edge cases and negative scenarios
- Build and maintain test-to-story traceability
- Plan regression coverage

## Useful Questions to Ask Cursor

### Test Scenario Planning
- "Generate test scenarios for [Story-ID] from acceptance criteria."
- "Which test scenarios should I cover for [Feature]?"
- "Draft a test plan for Sprint X stories."
- "Which integration scenarios are needed for [Epic]?"

### Acceptance Criteria Coverage
- "List all AC for [Story-ID] and map each to test scenarios."
- "Are there gaps in AC coverage for [Story-ID]?"
- "Which scenarios go beyond AC but are still important?"
- "Validate that planned scenarios cover all AC for Sprint X."

### Edge Cases & Negative Scenarios
- "Which edge cases apply to [Feature]?"
- "List negative scenarios for [Story-ID]."
- "What error conditions should be tested for [Component]?"
- "What boundary conditions exist for [Field/Process]?"

### Regression Planning
- "What existing functionality might be impacted by [Story-ID]?"
- "Generate regression scenarios for components modified in Sprint X."
- "Which previous stories touched [Component] and need re-validation?"
- "Plan a regression scenario suite for [Feature-Area]."

### Traceability
- "Map planned scenarios to JIRA stories for Sprint X."
- "Show traceability between [Story-ID] and impacted components."
- "List all components that need testing for [Epic]."

## Workflow

1. **Story Analysis** — review story details and AC
2. **Scenario Planning** — define positive, negative, edge cases
3. **Documentation** — capture detailed scenarios (steps + expected outcomes)
4. **Traceability** — map scenarios to stories and components
5. **Execution** — run tests in the appropriate environment (external to this workspace)
6. **Reporting** — document outcomes and defects

## Test Scenario Document Template

```markdown
# Test Scenarios: [Story-ID] — [Feature]

## Objective
[What is being validated]

## Prerequisites
- [Required data / setup]
- [Required permissions / profiles]
- [Environment state]

## Scenarios

### TS-001: [Scenario Title]
**Priority**: High / Medium / Low
**Type**: Functional / Integration / Regression

**Steps**:
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Outcome**:
- [Outcome 1]
- [Outcome 2]

**AC Covered**: AC-1, AC-3

---

### TS-002: [Negative Scenario]
**Priority**: High / Medium / Low
**Type**: Negative

**Steps**:
1. [Invalid input or state]
2. [Action]

**Expected Outcome**:
- [Validation error or controlled failure]

**AC Covered**: AC-2

## Test Data Requirements
[Data records, configuration, or fixtures needed]

## Dependencies
[Other stories or components]

## Traceability
- JIRA Story: [JIRA-ID]
- Components: [List]
```

## Artifacts to Create

- Test scenario documents → `/artifacts/test-plans/[story-id]-scenarios.md`
- Test coverage matrix → `/artifacts/test-plans/sprint-X-coverage.md`
- Regression scenario suites → `/artifacts/test-plans/regression-[feature].md`
- Test traceability reports → `/artifacts/analysis/test-traceability.md`

> Do **not** write Apex test classes, JavaScript test files, or automation scripts in this workspace.
