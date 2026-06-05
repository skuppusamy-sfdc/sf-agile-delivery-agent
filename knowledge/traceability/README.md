# /knowledge/traceability

Per-epic traceability matrices. Use `templates/traceability-matrix-template.md`.

## Convention

```
traceability/
  EPIC-12-traceability.md
  EPIC-15-traceability.md
```

A traceability matrix maps:

```
Story  ↔  AC  ↔  Component  ↔  Test Case  ↔  Solution Doc
```

Update when:
- A new story lands in the epic
- An AC is added/changed
- A test case is added
- A solution doc is authored

The auto-generated `knowledge/TRACEABILITY-INDEX.md` aggregates these into a program-wide view.
