# ADR-001: Use Permission Set Groups, not Profiles, for new access

> EXAMPLE — delete once your team has real ADRs.

**Status**: Accepted
**Date**: 2026-04-29
**Deciders**: J. Doe (SA), K. Lee (TA), M. Patel (Security)
**Related stories**: PROJ-007, PROJ-014, PROJ-021

## Context

Salesforce is deprecating Profile-based access control in favor of Permission Sets and Permission Set Groups. Our existing org has 18 custom Profiles, several of which overlap. New stories adding access need a consistent direction.

## Decision

All **new** access for any user persona is granted via a Permission Set or a Permission Set Group. We will not create new custom Profiles. Existing Profiles remain in place but will be progressively reduced to a Minimum Access baseline.

## Consequences

**Positive**
- Aligns with Salesforce's roadmap
- Composable per-feature access (one Permission Set per capability)
- Easier audit (one source of access per feature)

**Negative**
- Migration effort for existing Profile-based access (separate program of work)
- Devs must remember to author Permission Sets, not Profile diffs

**Neutral**
- License-based features (Object access controlled by License) still flow through Profiles

## Alternatives considered

- **Continue with Profile diffs** — rejected: not future-proof
- **Big-bang Profile migration** — rejected: risk too high, scope too large

## References
- [Salesforce: Migrate from Profiles to Permission Sets](https://help.salesforce.com/)
