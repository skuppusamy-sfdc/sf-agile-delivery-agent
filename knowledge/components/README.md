# /knowledge/components

Deeper write-ups for individual Salesforce components when a single metadata doc isn't enough — e.g., complex flows, OmniScripts, or Apex services with rich business logic.

## When to put a doc here vs in /knowledge/metadata

| Use `/metadata/` | Use `/components/` |
|---|---|
| Standard fields / objects | A flow with > 10 elements |
| Simple classes / triggers | A service class with multiple integration points |
| Validation rules | An OmniScript with branching logic |
| Permission sets | A custom LWC with custom data flow |

## Convention

```
components/
  OrderApprovalFlow.md
  OrderService-Apex.md
  CustomerOnboarding-Omni.md
```

Cross-link from `/metadata/<type>/<Component>.md` so readers find the deep dive.
