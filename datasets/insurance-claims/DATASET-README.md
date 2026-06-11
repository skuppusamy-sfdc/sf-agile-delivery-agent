# Synthetic Dataset: Insurance Claims Processing

## Overview

This is a **fully synthetic** dataset of 1,705 JIRA-style stories for a fictional Salesforce Insurance Claims Processing implementation project ("Acme Insurance"). It is designed to demonstrate and benchmark the SADA semantic index pipeline.

**No real company data is included.** All stories, names, processes, and technical details are AI-generated.

## Statistics

| Metric | Value |
|--------|-------|
| Total stories | 1,705 |
| Sprints | 20 (Sprint 1 – Sprint 20) |
| Phases | Phase 1 (Sprints 1-8), Phase 2 (Sprints 9-20) |
| Story type | 78% Story, 22% Bug |
| Themes/Epics | 17 |
| Total size | ~5.4 MB |

## Domain: Insurance Claims on Salesforce

This dataset models a Salesforce implementation for a mid-size insurance carrier covering:

- **Policyholder management** — policy lifecycle, coverage, beneficiaries
- **Provider network** — credentialing, contracting, fee schedules, termination
- **Claims processing** — FNOL intake, adjudication, payment, EOB
- **Agent/broker portal** — self-service, commission tracking
- **Compliance** — audit trails, regulatory reporting, COB

### Key Domain Terms

| Acronym | Meaning |
|---------|---------|
| FNOL | First Notice of Loss |
| LOB | Line of Business |
| TPA | Third Party Administrator |
| EOB | Explanation of Benefits |
| ERA | Electronic Remittance Advice |
| CPT | Current Procedural Terminology |
| ICD-10 | International Classification of Diseases |
| NPI | National Provider Identifier |
| TIN | Tax Identification Number |
| PNA | Provider Network Agreement |
| GSA | Group Service Agreement |
| PCN | Provider Change Notification |
| SIU | Special Investigations Unit |
| COB | Coordination of Benefits |
| MCO | Managed Care Organization |
| CAQH | Council for Affordable Quality Healthcare |

## Structure

```
knowledge/sprints/
  Sprint 1/stories/INS-0001.md ... INS-0060.md
  Sprint 2/stories/INS-0061.md ... INS-0135.md
  ...
  Sprint 20/stories/INS-1666.md ... INS-1705.md
```

Each story file follows this format:

```markdown
# INS-XXXX: Story title

- **Sprint**: Acme Insurance Sprint N (Phase X)
- **Status**: Done|In Test|In Progress|Open
- **Type**: Story|Bug
- **Priority**: High|Medium|Low
- **Epic**: Theme Name
- ... (other metadata)

## Description
As a [Role], I need [feature] so that [benefit].

## Acceptance Criteria
Given/When/Then with specific Salesforce object and field references.

## Solution
Technical implementation approach.
```

## How to Use

### Run SADA semantic index pipeline on this dataset:

```bash
# From the project root
cd scripts/semantic-index

# Point config to this dataset
# Edit config.yaml: corpus.sprints_dir = "datasets/insurance-claims/knowledge/sprints"

# Dry run
python3 build.py --dry-run

# Build glossary index
python3 build.py --index glossary
```

### Run RAG index scripts:

```bash
# Generate AC index
python3 scripts/create-ac-index.py

# Generate Solution index
python3 scripts/create-solution-index.py
```

## Generation Method

Generated using Claude Sonnet 4.6 via the SADA `gateway_direct` adapter with:
- 8 stories per LLM call
- 8,192 max output tokens
- Temperature 0.8 for diversity
- Structured prompts with domain vocabulary and theme distribution
- Retry logic for gateway disconnects

Total generation time: ~6 hours
Total LLM calls: ~215

## License

MIT License — Copyright (c) 2024-2026 Sakthi Kuppusamy

This dataset is synthetic and may be freely used for research, demonstration, and benchmarking.
