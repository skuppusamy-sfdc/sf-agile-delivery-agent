# Developer Guidelines (Plan & Design Only)

> This workspace is **strictly Plan / Ask / Design**. Code is **not** written here. All implementation happens in the separate Salesforce Dev / Sandbox environment and the code repository. Use this workspace to understand requirements, design the approach, and plan tests.
>
> **Companion skill:** `_cursor/skills/dev-story-prep/SKILL.md` — the AI auto-invokes this skill when the user asks to understand a story, plan an approach, identify edge cases, or plan unit-test scenarios. The skill and this guideline describe the same workflow; this file is for humans, the skill is for the bot. Keep them aligned when editing.

## Primary Activities in This Workspace

- Understand requirements and acceptance criteria
- Identify impacted components and dependencies
- Design the approach (in prose, not code)
- Plan unit-test scenarios (scenarios, not test classes)
- Capture open questions and risks before implementation

## Environment Clarification

- This workspace documents **deployed metadata** in `/knowledge/metadata/` (typically the QA environment)
- Code development happens in **Dev / Sandbox**
- Story requirements apply across all environments

## Useful Questions to Ask Cursor

### Understanding Requirements
- "Explain the requirements for [Story-ID] in technical terms."
- "List the acceptance criteria for [Story-ID]."
- "Which components are likely impacted by [Story-ID]?"
- "Are there dependencies I should be aware of for [Story-ID]?"

### Design Clarification
- "What is the recommended design approach for [Feature]?"
- "Which existing metadata is relevant when designing [Component]?"
- "What edge cases should be considered for [Story-ID]?"
- "How does [Component-A] interact with [Component-B]?"

### Unit-Test Planning (Scenarios)
- "What unit-test scenarios are needed for [Story-ID]?"
- "Map test scenarios to acceptance criteria for [Story-ID]."
- "What negative scenarios are relevant for [Component]?"
- "What test data setup is required for [Feature]?"

### Technical Questions
- "What metadata types are involved in [Story-ID]?"
- "Describe the data flow for [Process-Name]."
- "What validation rules are appropriate for [Object]?"
- "What security considerations apply to [Feature]?"

## Workflow

1. **Story Assignment** — read story details and acceptance criteria
2. **Clarification** — ask questions about unclear requirements
3. **Design** — capture approach, impacted components, dependencies
4. **Test Planning** — define unit-test scenarios (descriptions only)
5. **Hand-off** — implementation occurs in Dev / Sandbox; code lives in the code repository
6. **Post-Deployment** — optionally update metadata docs after deployment

## Artifacts to Reference

- Technical solutions → `/artifacts/solutions/`
- Component documentation → `/knowledge/components/`
- Deployed metadata → `/knowledge/metadata/`
- Architecture diagrams → `/artifacts/diagrams/`
- Traceability matrix → `/knowledge/traceability/`

## Unit-Test Scenario Plan (Description-Only Template)

```markdown
# Unit-Test Scenarios: [Story-ID]

## Component Under Test
[Component name and responsibility]

## Positive Scenarios
1. [Scenario]
   - Setup: [Conditions/data]
   - Expected: [Behavior]

## Negative Scenarios
1. [Scenario]
   - Setup: [Invalid input / state]
   - Expected: [Error behavior]

## Edge Cases
1. [Edge case scenario]

## Test Data Requirements
[What records / config / permissions are needed]

## Dependencies
[Components that need to be mocked or pre-existing]
```

> The template above describes scenarios in plain language. **Do not** write Apex test classes or executable test code in this workspace.
