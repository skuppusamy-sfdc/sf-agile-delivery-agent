# /knowledge/architecture

Architecture Decision Records (ADRs). One file per decision.

## Naming

```
architecture/
  ADR-001-permission-model.md
  ADR-002-integration-pattern.md
  ADR-003-record-sharing-strategy.md
  ...
```

Sequential, three-digit numbering. Use the QUICK-START recipe to scaffold.

## ADR template

```markdown
# ADR-NNN: [Short title]

**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Date**: YYYY-MM-DD
**Deciders**: [names]
**Related stories**: [STORY-IDs]

## Context
What is the issue we're addressing? What constraints exist?

## Decision
What did we decide? Be precise.

## Consequences
- Positive
- Negative
- Neutral

## Alternatives considered
- Option A — rejected because …
- Option B — rejected because …

## References
- [Salesforce docs link]
- [Prior ADRs]
```

## Lifecycle

- **Proposed** → under discussion
- **Accepted** → in force
- **Deprecated** → no longer recommended; existing implementations grandfathered
- **Superseded** → explicitly replaced by another ADR (cite it)

Never delete an ADR. Mark it superseded and keep the file for history.
