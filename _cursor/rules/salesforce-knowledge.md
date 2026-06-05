# Rule: Salesforce Knowledge Conventions

**Applies in**: all modes
**Why**: Salesforce has unique terminology, metadata types, and patterns. This rule keeps AI responses precise.

---

## Terminology to use precisely

| Use | Don't use |
|---|---|
| Object (sObject), Field, Record | "table", "column", "row" |
| Apex Class / Trigger | "Java", "function" |
| Lightning Web Component (LWC) | "Lightning component" (ambiguous — could mean Aura) |
| Flow (Screen / Record-Triggered / Auto-launched / Scheduled / Platform Event-Triggered) | just "Flow" without subtype |
| Validation Rule, Workflow Rule, Process Builder, Flow | one-size-fits-all "automation" |
| Permission Set, Permission Set Group, Profile, Public Group, Queue, Role | conflated as "user access" |
| Profile (legacy access control — being phased out) | always recommend Permission Sets for new access |
| Custom Metadata Type vs Custom Setting | these are different — don't conflate |
| Platform Event vs Change Data Capture vs Pub/Sub API | distinct integration patterns |
| OmniScript / Integration Procedure / DataRaptor (Industries / Vlocity) | only when project uses Industries Cloud |
| Agentforce / Einstein Generative AI / Prompt Template | new GenAI stack — only when project uses it |

---

## Metadata types frequently referenced

| Folder under `force-app/main/default/` | What lives there |
|---|---|
| `objects/<Object>/fields/` | field metadata (`*.field-meta.xml`) |
| `objects/<Object>/recordTypes/` | record types |
| `objects/<Object>/listViews/` | list views |
| `flows/` | `*.flow-meta.xml` |
| `classes/` | `*.cls` + `*.cls-meta.xml` |
| `triggers/` | `*.trigger` |
| `lwc/<component>/` | LWC bundles |
| `aura/<component>/` | Aura bundles |
| `permissionsets/` | `*.permissionset-meta.xml` |
| `profiles/` | `*.profile-meta.xml` |
| `staticresources/` | static resources |
| `genAiPromptTemplates/` | Agentforce prompt templates |
| `genAiFunctions/` | Agentforce functions |
| `genAiPlanners/`, `bots/` | Agentforce / Einstein Bot wiring |
| `omniScripts/`, `omniIntegrationProcedures/`, `omniDataTransforms/` | Industries Cloud (Vlocity) |

When the user names a component, infer the metadata type from the suffix and propose the correct path under their `metadata_repo.local_path`.

---

## Conventions for the knowledge workspace

### Story ID style
Use the regex from `workspace.config.yaml > story_id.pattern`. Don't assume a specific format.

### Naming
- Solution docs: `artifacts/solutions/{STORY-ID}-{kebab-slug}.md`
- ADRs: `knowledge/architecture/ADR-{NNN}-{kebab-slug}.md`
- Test scenario docs: `artifacts/test-plans/{STORY-ID}-scenarios.md`
- Metadata docs: `knowledge/metadata/{type}s/{ApiName}.md`

### Cross-references
Every solution and ADR should cite:
1. The story ID(s) it addresses
2. The components it impacts (link to `knowledge/metadata/...` if documented)
3. Related ADRs / prior solutions

---

## When in doubt

- If the user says "Flow" — ask which type
- If the user names a class — confirm whether it's Apex or LWC JS
- If the user mentions integration — clarify Platform Event vs CDC vs API vs ETL
- If the user says "Industries" or "Vlocity" — confirm whether OmniStudio components are in scope

A clarifying question is cheaper than a wrong answer.
