# User Story Traceability Matrix

> **Planning Artifact.** Connects JIRA stories, Copado stories, and Salesforce components for traceability and analysis. No code, no implementation — references only.

Place completed matrices in `/knowledge/traceability/sprint-[number]-traceability.md`.

---

## Sprint: [Sprint Number]

## Traceability Matrix

| JIRA Story | Copado Story | Salesforce Components | Metadata Types | Status | Notes |
|------------|--------------|-----------------------|----------------|--------|-------|
| STORY-123 | COPADO-456 | `Account__c.CustomField__c` | CustomField | Done | [Link] |
| STORY-124 | COPADO-457 | `OpportunityFlow` | Flow | In Progress | [Link] |
| STORY-125 | COPADO-458 | `AccountTriggerHandler` | ApexClass, ApexTrigger | To Do | [Link] |

## Component Impact Summary

### High Impact Components
Components touched by multiple stories or critical to business processes:

| Component | Stories Affecting | Risk Level | Notes |
|-----------|-------------------|------------|-------|
| [Component] | STORY-123, STORY-125 | High | [Why high risk] |

### New Components Planned
| Component | Story | Metadata Type | Purpose |
|-----------|-------|---------------|---------|
| [Component] | STORY-124 | Flow | [Purpose] |

### Components Deleted / Deprecated
| Component | Story | Reason | Replacement |
|-----------|-------|--------|-------------|
| [Component] | STORY-126 | [Reason] | [Replacement] |

## Cross-Sprint Dependencies

### Dependencies on Previous Sprints
| Current Story | Depends On | From Sprint | Status | Risk |
|---------------|------------|-------------|--------|------|
| STORY-125 | STORY-098 | Sprint 3 | Done | Low |

### Stories Impacting Future Sprints
| Current Story | Blocks | Planned Sprint | Notes |
|---------------|--------|----------------|-------|
| STORY-123 | STORY-150 | Sprint 6 | [Notes] |

## Epic Traceability

### Epic: [Epic Name]
| JIRA Story | Sprint | Status | Components |
|------------|--------|--------|------------|
| STORY-120 | Sprint 4 | Done | [Components] |
| STORY-123 | Sprint 5 | Done | [Components] |
| STORY-127 | Sprint 6 | In Progress | [Components] |

## Metadata Change Index (Reference)

### Objects
- **Account**: STORY-123 (added `CustomField__c`)
- **Opportunity**: STORY-124 (modified validation rule)

### Flows
- **OpportunityFlow**: STORY-124 (new flow planned)

### Apex (References Only — implementation lives in code repo)
- **AccountTriggerHandler**: STORY-125 (logic change planned)
- **OpportunityTrigger**: STORY-125 (new trigger planned)

## Test Traceability

| Story | Test Scenario Set | Test Status | Defects |
|-------|-------------------|-------------|---------|
| STORY-123 | TS-123 | Passed | None |
| STORY-124 | TS-124 | In Progress | DEF-001 |

## Notes & Decisions

[Important decisions, assumptions, or context relevant to traceability.]
