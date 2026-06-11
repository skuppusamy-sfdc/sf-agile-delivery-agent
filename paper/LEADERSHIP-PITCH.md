# SADA — Salesforce Agile Delivery Agent
## Leadership Quick-Sell Canvas (3 Slides)

---

## SLIDE 1: What SADA Does

### One-Line

> Build semantic intelligence into your delivery knowledge **once** — query it forever, with **any tool, any model, zero lock-in**.

### The Problem

- Agile delivery teams drown in 1,000+ stories across sprints — context is lost, conflicts are missed, onboarding is slow
- Current AI solutions require specific models, vector databases, and vendor lock-in
- When the model changes or the tool changes, you start over

### SADA's Approach

| Principle | How |
|-----------|-----|
| **Any Tool** | Works with Cursor, Claude Code, VS Code, ChatGPT, or any AI assistant — outputs are standard JSON files |
| **Any Model** | Built and queryable with Claude, GPT, Gemini, Llama, or any LLM — provider adapters are swappable |
| **No Lock-In** | Semantic indexes are flat JSON — portable, version-controlled, grep-able, model-independent |
| **Build Once** | LLM extracts domain knowledge at build time → indexes persist regardless of tool/model changes |

### What Gets Built (6 Semantic Indexes)

| Index | What It Captures |
|-------|-----------------|
| **Domain Glossary** | Every acronym, role, process, status value — auto-extracted from stories |
| **Semantic Similarity** | Phrases that mean the same thing mapped explicitly (no embedding drift) |
| **Story Summaries** | One-line intent + structured entities per story |
| **Business Rules** | IF/WHEN/THEN logic extracted from Acceptance Criteria |
| **Cross-Story Links** | Non-obvious dependencies, conflicts, regressions |
| **Intent Mapping** | Natural language questions → relevant stories and processes |

---

## SLIDE 2: Who Benefits — Ideal Customer

### Sweet Spot

| Criteria | Detail |
|----------|--------|
| **Platform** | Salesforce (any cloud — Health, Financial Services, Industries) |
| **Scale** | 500+ JIRA stories across multiple sprints |
| **Pain** | Cross-team dependencies, knowledge silos, slow onboarding |
| **Delivery Model** | Agile/Scrum with SA, TA, Dev, QA roles |

### Role-Specific Value

| Role | Before SADA | With SADA |
|------|------------|-----------|
| **Solution Architect** | Manually grep across sprints for conflicts | Semantic conflict detection surfaces risks automatically |
| **Technical Architect** | Re-read 50 stories to find patterns | "What components touch Account?" answered instantly |
| **Developer** | Spend 15 min understanding a story's context | Full domain context + related stories in seconds |
| **Tester** | Write test scenarios from scratch per story | Structured business rules → test scenarios auto-mapped |

### Tool & Model Agnostic — Works Everywhere

```
┌─────────────────────────────────────────────────────────┐
│              SADA Semantic Indexes (JSON)                 │
│   Glossary | Similarity | Rules | Links | Intents       │
└──────────────────────────┬──────────────────────────────┘
                           │
          Used by ANY of these (no changes needed):
                           │
     ┌─────────┬───────────┼───────────┬──────────┐
     │         │           │           │          │
  Cursor    Claude      VS Code     ChatGPT    Custom
   AI       Code       Copilot      / GPT      Agent
```

---

## SLIDE 3: What's Needed — Setup

### Prerequisites (You Already Have These)

| Requirement | Why |
|-------------|-----|
| JIRA access | Standard HTML export of sprint stories |
| Any LLM access | Claude, GPT, Gemini, or local model — one-time extraction |
| Python 3.9+ | Runs the build scripts |
| Any AI tool | Cursor, Claude Code, VS Code, ChatGPT — indexes work with all |

### NOT Needed

- No vector database
- No GPU or dedicated infrastructure
- No specific model vendor commitment
- No ongoing API subscriptions for retrieval

### 3-Day Setup

| Day | Action | Output |
|-----|--------|--------|
| **1** | Import JIRA stories (HTML export → markdown split) | Per-story searchable files |
| **2** | Run semantic extraction (any LLM, any provider) | 6 JSON semantic indexes |
| **3** | Team starts using with their preferred AI tool | Full domain-aware retrieval |

### Architecture: Tool & Model Independence

```
BUILD (one-time, any model)         USE (ongoing, any tool)
────────────────────────────        ────────────────────────
Stories + Any LLM                   Any AI Assistant
    │                                   │
    ▼                                   ▼
┌──────────────┐                 ┌──────────────┐
│ Provider     │                 │ Read JSON    │
│ Adapters:    │                 │ files from   │
│ • Claude     │                 │ any tool:    │
│ • GPT        │  ──► JSON ──►  │ • Cursor     │
│ • Gemini     │    indexes     │ • Claude Code│
│ • Llama      │                 │ • ChatGPT   │
│ • Any API    │                 │ • Custom    │
└──────────────┘                 └──────────────┘
```

### Pilot Proposal

Pick one active program → import stories → run extraction → measure:
1. **Query speed**: Time to answer "what conflicts with this story?"
2. **Onboarding**: New team member ramp-up time
3. **Quality**: Defects caught at planning vs. discovered in UAT

---

**GitHub**: github.com/skuppusamy-sfdc/sf-agile-delivery-agent
**Author**: Sakthi Kuppusamy | MIT License
