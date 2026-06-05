# SF Agile Delivery Agent

A tool-agnostic semantic index builder for Salesforce agile delivery projects. Uses LLM-at-build-time to extract domain knowledge from JIRA story exports, producing flat JSON indexes that enable zero-cost semantic search at query time.

## What It Does

Processes your JIRA story corpus (markdown files) through any LLM provider **once**, extracting:

| Index | Purpose | Output |
|-------|---------|--------|
| **Glossary** | Domain terms, acronyms, roles, systems | `SEMANTIC-GLOSSARY.json` |
| **Story Summaries** | One-line summaries + structured entity extraction | `STORY-SUMMARIES.json` |
| **Business Rules** | Structured IF/WHEN/THEN rules from AC | `BUSINESS-RULES.json` |
| **Semantic Similarity** | Groups of equivalent phrases | `SEMANTIC-SIMILARITY.json` |
| **Cross-Story Links** | Non-obvious semantic relationships | `CROSS-STORY-LINKS.json` |
| **Intent Mapping** | User queries → processes → stories | `INTENT-MAP.json` |

## Architecture

```
BUILD TIME (one-time cost)          QUERY TIME (zero cost)
─────────────────────────           ─────────────────────
Stories (.md files)                  User query
        │                                  │
        ▼                                  ▼
┌─────────────────────┐            ┌──────────────────┐
│  Prompt Templates   │            │  Lookup in JSON  │
│  + Output Schemas   │            │  indexes (fast)  │
└────────┬────────────┘            └──────────────────┘
         │
         ▼
┌─────────────────────┐
│  LLM Provider       │
│  (any adapter)      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Semantic Indexes   │
│  (flat JSON files)  │
└─────────────────────┘
```

## Provider Adapters

| Adapter | Use Case | Dependencies |
|---------|----------|-------------|
| `gateway_direct` | Salesforce LLM Gateway (Bedrock proxy) | `httpx` |
| `anthropic_direct` | Direct Anthropic API | `anthropic` SDK |
| `anthropic_batch` | Anthropic Batch API (50% off) | `anthropic` SDK |
| `openai_batch` | OpenAI Batch API (50% off) | `openai` SDK |
| `file_based` | Manual — write prompts to files, process anywhere | None |

## Quick Start

```bash
# 1. Configure (edit config.yaml for your adapter/models)
cd scripts/semantic-index

# 2. Dry run — see how many requests will be made
python3 build.py --dry-run

# 3. Build a single index
python3 build.py --index glossary

# 4. Build all indexes
python3 build.py

# 5. Resume if interrupted (adapter saves progress incrementally)
python3 build.py --index glossary --resume <batch-id>
```

## Prerequisites

- Python 3.9+
- JIRA stories exported as per-story markdown files in `knowledge/sprints/*/stories/*.md`
- One of:
  - Salesforce LLM Gateway access (`ANTHROPIC_BEDROCK_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`)
  - Anthropic API key (`ANTHROPIC_API_KEY`)
  - OpenAI API key (`OPENAI_API_KEY`)
  - Or just use `file_based` adapter (no API needed)

## Story Markdown Format

Each story file should have this structure:

```markdown
# PROJ-1234: Story title here

- **Sprint**: Sprint 5
- **Status**: Done
- **Type**: Story
- **Epic**: Feature Name
- **Components**: ComponentA, ComponentB

## Description

As a [role], I need [feature] so that [benefit].

## Acceptance Criteria

Given [context]
When [action]
Then [expected result]

## Solution

Technical approach description...
```

## Configuration

Edit `scripts/semantic-index/config.yaml`:

```yaml
adapter: gateway_direct  # Your LLM provider

models:
  glossary: claude-sonnet-4-6
  story_summaries: claude-haiku-4-5-20251001
  business_rules: claude-haiku-4-5-20251001
  # Use cheaper models for high-volume extraction tasks

batch_size:
  glossary: 40        # Stories per LLM request
  story_summaries: 15
  business_rules: 10

corpus:
  sprints_dir: knowledge/sprints
  story_pattern: "*/stories/*.md"
```

## Customization

- **Prompt templates** (`prompts/*.md`): Edit to tune extraction for your domain
- **Output schemas** (`schemas/*.json`): Modify to change the structure of extracted data
- **Adapters** (`adapters/`): Add new providers by implementing `BatchAdapter`

## Project Structure

```
scripts/semantic-index/
├── build.py              # Main CLI orchestrator
├── prepare.py            # Corpus loader + prompt renderer
├── assemble.py           # Response parser + deduplication
├── validate.py           # JSON Schema validation
├── config.yaml           # Provider/model/batch config
├── adapters/
│   ├── base.py           # Abstract adapter interface
│   ├── gateway_direct.py # Salesforce LLM Gateway
│   ├── anthropic_direct.py
│   ├── anthropic_batch.py
│   ├── openai_batch.py
│   └── file_based.py    # Zero-dependency fallback
├── prompts/              # LLM prompt templates
│   ├── glossary.md
│   ├── story-summary.md
│   ├── business-rules.md
│   ├── semantic-similarity.md
│   ├── cross-story-links.md
│   └── intent-mapping.md
└── schemas/              # Output validation schemas
    └── *.schema.json
```

## License

MIT License - Copyright (c) 2024-2026 Sakthi Kuppusamy
