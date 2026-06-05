# START HERE (v2)

Welcome. This document gets you productive in **5 minutes** — and explains *why* each step exists, so nothing feels magic.

> **In a hurry?** Run the four commands in **§2** and skip to **§3**. Come back for the explanations when something breaks.

> **What's new in v2?** The AI is **strictly Plan / Ask only** — it will never write code, never offer to switch to build mode, never ask "should I implement this?". Each role also has a **companion Skill** that auto-fires on intent. See `CHANGELOG-v2.md` for the full delta.

---

## 1. What is this workspace?

A code-free, plan-and-design Cursor workspace for a Salesforce program. It holds:

- **Requirements** (sprint HTML exports from JIRA → indexed automatically)
- **Solutions** (tech design reviews and augmentations the AI helps draft)
- **Traceability** (story ↔ component ↔ AC ↔ test maps)
- **Architecture** (decisions, diagrams)
- **Metadata** (`/knowledge/metadata/` — source of truth for what's deployed)

It also holds a **clone of the Salesforce metadata repo** (`/knowledge/metadata/`) so the AI can search Flows, Apex classes, Integration Procedures, and other deployed components directly.

### Mental model

```
Seed (in shared Drive)          Per-project working copy
────────────────────             ───────────────────────────
salesforce-knowledge-      ─cp─► acme-knowledge/
workspace-template_v2/             ├─ mv _cursor .cursor       ← Cursor wakes up
                                   ├─ cp config example→live   ← project identity set
                                   └─ drop sprint HTML         ← indexes auto-build
                                                                  → AI is productive
```

Each step below is **reversible and idempotent**. If you mis-rename or mis-configure, just redo the step — nothing is destructive.

---

## 2. First-time setup (run once)

### Step 2.1 — **Copy** the template into a new project location

```bash
# From inside the shared Drive folder where the template lives:
cp -R salesforce-knowledge-workspace-template_v2/ ~/projects/acme-knowledge/
cd ~/projects/acme-knowledge/
```

**Why a copy, not a clone?** The template is a *seed*. Each program forks its own working copy so:

- Project-specific config doesn't leak back into the seed
- `workspace.config.yaml` (with paths to *your* machine) stays out of the shared Drive
- Multiple programs can run from the same seed without collision

> **Tip**: If you want version-controlled history, run `git init && git add . && git commit -m "init from template v2"` immediately after the copy. Don't reuse the seed's git history.

---

### Step 2.2 — **Rename** the cursor folder

```bash
mv _cursor .cursor
```

**Why this exists.** Cursor only loads AI rules from a literal `.cursor/` folder. But Cursor itself blocks *creating* `.cursor/` programmatically inside a managed workspace — that's why the seed ships the folder as `_cursor/` and asks the human to flip the name once on their own machine.

**What you get after the rename:**

| File / Folder | What it does |
|---|---|
| `.cursor/AGENTS.md` | Umbrella behavior rules (strict Plan/Ask, Salesforce-knowledge focus, traceability-first) |
| `.cursor/rules/plan-and-ask-only.mdc` | **(NEW v2)** AI refuses to write code, never asks to switch modes |
| `.cursor/rules/metadata-is-source-of-truth.mdc` | **(NEW v2)** `/knowledge/metadata/` wins over JIRA Solution for current-state facts |
| `.cursor/rules/no-code-development.md` | Companion to plan-and-ask-only — additional guardrails |
| `.cursor/rules/token-optimization.md` | Forces the AI to read indexes before raw HTML — saves $$$ on long sprints |
| `.cursor/rules/salesforce-knowledge.md` | Keeps Salesforce terminology precise (Flow types, Permission Sets vs Profiles, OmniStudio, Agentforce) |
| `.cursor/skills/ta-historic-context/SKILL.md` | **(NEW v2)** Auto-fires when the user asks the TA to design / review / augment |
| `.cursor/skills/sa-cross-sprint-consistency/SKILL.md` | **(NEW v2)** Auto-fires for SA conflict / AC / dependency questions |
| `.cursor/skills/dev-story-prep/SKILL.md` | **(NEW v2)** Auto-fires for dev story-prep / unit-test scenario questions |
| `.cursor/skills/qa-test-scenarios/SKILL.md` | **(NEW v2)** Auto-fires for QA scenario / coverage / regression questions |

Open the folder in Cursor and you should see the rules and skills loaded in the Cursor settings panel.

---

### Step 2.3 — **Configure** the workspace

```bash
cp workspace.config.example.yaml workspace.config.yaml
$EDITOR workspace.config.yaml
```

The `.example` file ships with the template and is committed to git. Your live `workspace.config.yaml` is **gitignored** so per-developer paths and real project names never get pushed back to the seed.

**Minimum fields to change:**

| Field | What to set | Why it matters |
|---|---|---|
| `project.name` | Your program's display name | Appears in every generated index header |
| `project.short_code` | 3–6 char slug | Used for filename conventions if you choose |
| `story_id.pattern` | Regex matching your JIRA IDs | Default `^[A-Z]+-\d+$` (e.g. `PROJ-123`). Change to e.g. `^PR\d+-\d+$` if your IDs are prefixed numeric |
| `story_id.jira_base_url` | Your JIRA browse URL | Lets future enhancements link directly to JIRA |
| `metadata_repo.local_path` | Path to your DX repo on disk | Required only for `catalog-metadata-components.py` |
| `metadata_repo.metadata_root` | Usually `force-app/main/default` | Override only if your DX repo layout is non-standard |
| `sprints.folder_pattern` | Default `Sprint {n}` | Change if you organize by `Iteration N`, `PI 25.1 Sprint 1`, etc. |

**Everything else** can stay on defaults until you hit a reason to change it.

---

### Step 2.4 — **(Optional) Initialize git**

```bash
git init && git add . && git commit -m "init from template v2"
```

Recommended even for a one-person workspace — it gives you a safe undo when an AI edit goes sideways.

---

### Setup complete — sanity check

After Steps 2.1–2.3, you should see:

- Cursor shows a green check next to `.cursor/AGENTS.md` (AI rules loaded)
- The 4 role skills appear in the Cursor skills panel
- The workspace name appears in the top bar

---

## 3. Drop your first sprint

> **Export format must be HTML — not CSV, not pasted text.** JIRA stories often have AC bullets or Solution paragraphs that have been **struck through** to indicate "no longer in scope" or "superseded." HTML preserves that markup; CSV flattens it and the AI can no longer tell live content from withdrawn content. The `jira-html-parsing.mdc` rule tells the AI to ignore `<s>` / `<strike>` / `<del>` / `text-decoration: line-through` content as non-authoritative, but only HTML carries those signals.

```bash
# Export Sprint 1 from JIRA: Issues → JQL search → Export → HTML (Current fields)
mkdir -p "knowledge/sprints/Sprint 1"
cp ~/Downloads/sprint1-export.html "knowledge/sprints/Sprint 1/"

# Split into per-story markdown (run first — enables precise RAG retrieval)
python scripts/split-sprint-stories.py --sprint "Sprint 1"

# Build all indexes
python scripts/parse-sprint-html.py
python scripts/create-ac-index.py
python scripts/create-solution-index.py
python scripts/create-component-story-map.py
python scripts/create-feature-epic-map.py
python scripts/create-dependency-graph.py
```

**What appears (all auto-generated, all gitignored):**

| File | Contents |
|---|---|
| `knowledge/sprints/Sprint 1/stories/*.md` | One markdown file per story with full AC, Solution, Description |
| `knowledge/sprints/MASTER-STORY-INDEX.md` | Flat table: every story across every sprint |
| `knowledge/sprints/SPRINT-INDEX.md` | Per-sprint counts (Done / In Progress / Other) + headlines |
| `knowledge/AC-INDEX.md` | Every Acceptance Criteria across the program |
| `knowledge/SOLUTION-INDEX.md` | Every Solution column across the program |
| `knowledge/COMPONENT-TO-STORY-MAP.md` | Component → which stories touch it (highlights "≥ 2 stories" hot zones — your conflict candidates) |
| `knowledge/FEATURE-TO-STORY-MAP.md` | Epic / Feature → child stories |
| `knowledge/DEPENDENCY-GRAPH.md` | Story → other stories it references (with a Mermaid diagram) |

> **Why these are gitignored:** they're regeneratable. If two devs pulled them, every sprint drop would create a noisy merge conflict. Run the scripts locally, read the indexes, throw them away.

---

## 4. Ask Cursor your first question

Try (in Ask mode):

> "What stories were added in Sprint 1 and which components do they touch?"

Cursor will read `SPRINT-INDEX.md` and `COMPONENT-TO-STORY-MAP.md` first (~300 tokens) instead of opening the raw 10K-line HTML (~12K tokens). That's the **token-optimization rule** working.

### Try the role skills (v2)

The skills auto-fire when your question matches their trigger phrasing:

- *"Review the technical solution for STORY-101"* → TA skill fires, produces a review/augmentation artifact
- *"Find conflicts in Sprint 1"* → SA skill fires, produces a conflict report
- *"What edge cases should I watch for implementing STORY-101?"* → Dev skill fires, produces a dev prep brief
- *"Test scenarios for STORY-101"* → QA skill fires, produces a scenario doc with AC coverage map

You don't need to invoke skills explicitly — Cursor matches your question to the skill's trigger description.

---

## 5. Write your first solution

The TA skill is the easiest path:

> *"Review the technical solution for STORY-101."*

The skill fires, reads `Solution` + `AC` from the sprint HTML, pulls historic context from prior sprints + `/knowledge/metadata/`, classifies the Solution as complete / partial / missing / conflicting, and writes the right artifact to `artifacts/solutions/`.

Or do it manually:

```bash
cp templates/technical-solution-template.md \
   "artifacts/solutions/STORY-101-customer-onboarding.md"
$EDITOR "artifacts/solutions/STORY-101-customer-onboarding.md"
```

> **v2 note:** the AI will not generate Apex / LWC / metadata XML for the Solution. It produces design markdown only.

---

## 6. Clone the metadata repo and catalog it

Clone your Salesforce DX repo into `knowledge/metadata/` so the AI can search actual deployed metadata (Flows, Apex, IPs, OmniScripts, etc.):

```bash
# Clone the QA/main branch into knowledge/metadata/
git clone --depth 1 <your-sf-repo-url> knowledge/metadata/<repo-name>
```

Then generate the component catalog:

```bash
python scripts/catalog-metadata-components.py
```

This writes `knowledge/metadata/COMPONENT-CATALOG.md` — a flat inventory of every Apex class, Flow, object, LWC, etc. grouped by metadata type. The AI uses the **actual metadata files** (not just the catalog) to search for error messages, field references, and validation logic.

> **Source of truth:** `/knowledge/metadata/` is the **source of truth for current state**. When the JIRA `Solution` for a story disagrees with what's actually deployed, the metadata wins. See `rules/metadata-is-source-of-truth.mdc`.

---

## 7. Where to go next

| You are a … | Read |
|---|---|
| Solution Architect | `guidelines/solution-architect.md` (or just ask — `sa-cross-sprint-consistency` skill auto-fires) |
| Technical Architect | `guidelines/technical-architect.md` (or just ask — `ta-historic-context` skill auto-fires) |
| Developer | `guidelines/developer.md` (or just ask — `dev-story-prep` skill auto-fires) |
| Tester | `guidelines/tester.md` (or just ask — `qa-test-scenarios` skill auto-fires) |
| Anyone, end-to-end | `WORKFLOW-GUIDE.md` |
| Looking for copy-paste recipes | `QUICK-START.md` |
| Curious what changed from v1 | `CHANGELOG-v2.md` |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Cursor doesn't pick up rules | Folder is still `_cursor/` | `mv _cursor .cursor` |
| Scripts print *"workspace.config.yaml not found"* | You skipped Step 2.3 | `cp workspace.config.example.yaml workspace.config.yaml` |
| Scripts run but find 0 stories | `story_id.pattern` regex doesn't match your real IDs | Edit `story_id.pattern` in your config; rerun `python scripts/parse-sprint-html.py` |
| `parse-sprint-html.py` finds 0 stories despite HTML present | JIRA export uses non-standard column classes | Edit `COLUMN_HINTS` at the top of `scripts/parse-sprint-html.py` |
| `catalog-metadata-components.py` says "path not set" | `metadata_repo.local_path` is empty or wrong | Set it to the absolute path of your DX repo on this machine |
| AI says metadata files "don't exist" but they're on disk | `.gitignore` has blanket rules (`*.cls`, `force-app/`, etc.) that block Cursor's Glob tool | Remove or scope those rules — see the `.gitignore` comments. Grep and Shell still work as a fallback |
| AI tries to write Apex code | Rules not loaded (see row 1) or you're in a fresh Cursor session that hasn't reloaded `.cursor/` | Reload the window in Cursor |
| Skill doesn't auto-fire | Your phrasing doesn't match the skill's trigger description | Either rephrase, or read `_cursor/skills/<name>/SKILL.md` and follow the workflow manually |
