# Rule: No Code Development

**Applies in**: all modes (Ask, Plan, Agent)

This is a **knowledge workspace**, not a code editor. Production source code (Apex, LWC, Aura, Visualforce, Flow XML, custom metadata XML, JS in package code, etc.) **does not live here** and **must not be authored here**.

> See also: `plan-and-ask-only.mdc` (stricter, additive — Plan/Ask mode only with no mode-switch nudging) and `metadata-is-source-of-truth.mdc`.

---

## What "no code" means

| Allowed | Not allowed |
|---|---|
| Pseudocode in markdown to illustrate a concept | Full Apex classes / triggers |
| Inline SOQL/SQL snippets to clarify a query in a doc | A `.cls`, `.trigger`, `.js`, `.html`, `.flow-meta.xml` file |
| Mermaid / PlantUML diagrams | LWC component scaffolding |
| Bash one-liners in QUICK-START / scripts/ utility code | A copy of the metadata repo |
| Python utility scripts in `scripts/` (workspace tooling) | New Salesforce metadata files |

---

## When the user asks for code

1. Confirm whether they want **documentation pseudocode** (OK) or **production code** (refuse politely).
2. If production code: redirect to the metadata repo. Suggest the file path where it should land. Offer to write the **design** here and the **implementation guide** as markdown.
3. If pseudocode: keep it short, in fenced markdown, and label it `// pseudocode` or similar.

### Suggested response template

> "Production code lives in your Salesforce DX repo (`metadata_repo.local_path` in `workspace.config.yaml`), not here. I can:
>
> 1. Write a detailed implementation guide in `artifacts/solutions/[STORY-ID]-[slug].md` that your developer can follow,
> 2. Sketch the data model / class skeleton in pseudocode inside that doc, and
> 3. Generate a sequence diagram and a list of files to create in the DX repo.
>
> Want me to do all three?"

> **v2 note:** the suggested response above predates the strict `plan-and-ask-only.mdc` rule. Under v2, do **not** ask "want me to do all three?" — produce the design artifact directly without offering to switch modes or asking permission to implement.

---

## Why this matters

- **Auditability** — every line of production code goes through the DX repo's PR process; nothing can sneak in via the knowledge workspace
- **Single source of truth** — duplicate code in two repos drifts within days
- **Token cost** — refusing to author code keeps AI conversations focused and cheap
- **Role clarity** — Architects and Tech Architects design here; developers implement there

---

## Exceptions

The `scripts/` folder is workspace tooling (Python). Editing those scripts is fine — they're not Salesforce code.
