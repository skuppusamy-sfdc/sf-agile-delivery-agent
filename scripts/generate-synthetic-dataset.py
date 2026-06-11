#!/usr/bin/env python3
"""
Synthetic Dataset Generator — Insurance Claims Processing domain.

Generates ~1,805 realistic JIRA-style story markdown files for use as a
public demonstration corpus for the SADA semantic index pipeline.

Uses the LLM Gateway to generate stories in batches of 15-20.
Saves incrementally — safe to interrupt and resume.

Usage:
    python3 scripts/generate-synthetic-dataset.py                    # Generate all sprints
    python3 scripts/generate-synthetic-dataset.py --sprint 1         # Generate one sprint
    python3 scripts/generate-synthetic-dataset.py --dry-run          # Show plan without calling LLM
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "insurance-claims" / "knowledge" / "sprints"

# --- LLM Gateway Config ---
BASE_URL = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL", "").replace("/bedrock", "").rstrip("/")
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
CERT_PATH = os.environ.get("NODE_EXTRA_CA_CERTS", "")
MODEL = "claude-sonnet-4-6"

# --- Sprint Plan ---
SPRINT_PLAN = [
    {"sprint": 1, "stories": 60, "phase": "Phase 1", "focus": "Platform setup, basic objects, permission model"},
    {"sprint": 2, "stories": 75, "phase": "Phase 1", "focus": "Policyholder 360 views, Provider 360 account pages"},
    {"sprint": 3, "stories": 85, "phase": "Phase 1", "focus": "Provider Credentialing workflows, NPI validation"},
    {"sprint": 4, "stories": 90, "phase": "Phase 1", "focus": "Claims intake (FNOL), basic adjudication rules"},
    {"sprint": 5, "stories": 95, "phase": "Phase 1", "focus": "Provider Network Contracting, fee schedules"},
    {"sprint": 6, "stories": 100, "phase": "Phase 1", "focus": "Agent/Broker Portal MVP, self-service features"},
    {"sprint": 7, "stories": 95, "phase": "Phase 1", "focus": "Claims Payment & Disbursement, EOB generation"},
    {"sprint": 8, "stories": 90, "phase": "Phase 1", "focus": "UAT bugs from Phase 1, regression fixes"},
    {"sprint": 9, "stories": 85, "phase": "Phase 2", "focus": "Enhanced policyholder views, coverage history"},
    {"sprint": 10, "stories": 100, "phase": "Phase 2", "focus": "Provider Termination flows, network exit automation"},
    {"sprint": 11, "stories": 105, "phase": "Phase 2", "focus": "Fee Schedule automation, rate change notifications"},
    {"sprint": 12, "stories": 100, "phase": "Phase 2", "focus": "Agent Portal enhancements, commission tracking"},
    {"sprint": 13, "stories": 110, "phase": "Phase 2", "focus": "Cross-functional integration, data migration"},
    {"sprint": 14, "stories": 95, "phase": "Phase 2", "focus": "Agentforce AI claims processing, automation"},
    {"sprint": 15, "stories": 90, "phase": "Phase 2", "focus": "UAT bugs + enhancements from Phase 2 testing"},
    {"sprint": 16, "stories": 85, "phase": "Phase 2", "focus": "Reporting & analytics dashboards"},
    {"sprint": 17, "stories": 80, "phase": "Phase 2", "focus": "Provider data maintenance, bulk updates"},
    {"sprint": 18, "stories": 75, "phase": "Phase 2", "focus": "Compliance & audit trails, regulatory reporting"},
    {"sprint": 19, "stories": 50, "phase": "Phase 2", "focus": "Regression fixes, performance optimization"},
    {"sprint": 20, "stories": 40, "phase": "Phase 2", "focus": "Hypercare, stabilization, knowledge transfer"},
]

# --- Theme Distribution per Sprint ---
THEMES = [
    "Policyholder 360",
    "Provider Network Contracting",
    "Provider Credentialing",
    "Provider Termination",
    "Platform Readiness",
    "Agent/Broker Recruitment",
    "Provider 360",
    "Provider Data Maintenance",
    "Agent Portal",
    "Claims Payment & Disbursement",
    "Group/Employer Onboarding",
    "Agentforce (Claims AI)",
    "Uncategorized",
    "Phase 1 Cancelled",
    "Tech Debt",
    "E2E Testing",
    "Value-Based Care Reporting",
]

TEAM_MEMBERS = [
    "Sarah Chen", "Marcus Johnson", "Priya Patel", "David Kim", "Rachel Torres",
    "James Wright", "Anika Gupta", "Michael Brown", "Lisa Park", "Carlos Rodriguez",
    "Emily Watson", "Kevin Nguyen", "Amanda Foster", "Ryan Mitchell", "Sofia Hernandez",
]

COMPONENTS = [
    "ClaimsProcessing", "ProviderNetwork", "PolicyholderExperience",
    "AgentPortal", "PaymentEngine", "CredentialingService",
    "NetworkContracting", "ComplianceReporting", "DataIntegration",
    "Agentforce", "BrokerManagement", "FeeScheduleEngine",
]


def build_generation_prompt(sprint_num: int, phase: str, focus: str,
                            batch_start_id: int, batch_size: int,
                            story_type_ratio: str = "80% Story, 20% Bug") -> str:
    """Build the prompt for generating a batch of stories."""
    return f"""You are generating synthetic JIRA stories for a Salesforce Insurance Claims Processing implementation project. This is for a PUBLIC DATASET — generate realistic but entirely fictional content.

## Context
- Sprint: Acme Insurance Sprint {sprint_num} ({phase})
- Sprint Focus: {focus}
- Generate exactly {batch_size} stories
- Story IDs: INS-{batch_start_id:04d} through INS-{batch_start_id + batch_size - 1:04d}
- Type ratio: {story_type_ratio}

## Domain: Insurance Claims Processing on Salesforce
Key objects: Policy__c, Claim__c, Provider__c (Person Account), Facility__c (Business Account), Provider_Network_Agreement__c (PNA), Fee_Schedule__c, Group_Service_Agreement__c (GSA), Claim_Line__c, Payment__c, Explanation_of_Benefits__c (EOB), Provider_Change_Notification__c (PCN), Credentialing_Case__c, Network_Termination_Case__c
Key roles: Claims Operations Manager, Provider Network Specialist, Credentialing Specialist, Broker Relations Coordinator, Assignment Coordinator, Provider Relations Specialist, Underwriting Analyst, Compliance Officer
Key acronyms: FNOL (First Notice of Loss), LOB (Line of Business), TPA (Third Party Administrator), EOB (Explanation of Benefits), ERA (Electronic Remittance Advice), CPT (Current Procedural Terminology), ICD-10, NPI, TIN, PNA, GSA, PCN, SIU (Special Investigations Unit), COB (Coordination of Benefits), MCO (Managed Care Organization)
Key integrations: DocuSign, Conga CLM, QGenda, Workday, CMS (Centers for Medicare & Medicaid Services), CAQH, NPPES

## Themes to distribute across these {batch_size} stories (pick from):
{', '.join(THEMES[:12])}

## Team Members (pick assignees/reporters from):
{', '.join(TEAM_MEMBERS)}

## Components (pick from):
{', '.join(COMPONENTS)}

## Output Format
Output ONLY valid JSON — an array of story objects. Each story must have ALL these fields:

```json
[
  {{
    "id": "INS-{batch_start_id:04d}",
    "summary": "Short summary of the story",
    "sprint": "Acme Insurance Sprint {sprint_num} ({phase})",
    "status": "Done|In Test|In Progress|Open",
    "type": "Story|Bug",
    "priority": "High|Medium|Low",
    "resolution": "Done|Unresolved",
    "assignee": "Team Member Name",
    "reporter": "Team Member Name",
    "components": "Component1, Component2",
    "epic": "Theme Name (from list above)",
    "story_points": 1|2|3|5|8,
    "labels": "Phase1|Phase2, optional others",
    "description": "As a [Role], I need [feature] so that [benefit]. (For bugs: steps to reproduce, expected vs actual)",
    "acceptance_criteria": "Given/When/Then format with specific field names and values. Multiple criteria separated by newlines. Include Salesforce object and field references.",
    "solution": "Technical approach using Salesforce components (Flows, Apex, LWC, OmniStudio, etc.)"
  }}
]
```

## Quality Rules
1. ACs must reference specific Salesforce objects and fields (e.g., "Claim__c.Status__c = 'Adjudicated'")
2. For Bug type: description has steps to reproduce; AC may be empty or "as per Description"
3. Use domain acronyms naturally (FNOL, LOB, TPA, EOB, etc.)
4. ~10% of stories should reference other story IDs (e.g., "Extends INS-{max(1, batch_start_id-30):04d}")
5. Vary complexity: some stories have 1-2 ACs, others have 5-10 detailed ACs
6. Include realistic Salesforce technical terms in Solution (Record-Triggered Flow, Platform Event, Apex Trigger, OmniScript, DataRaptor, FlexCard, Permission Set Group, Sharing Rule)
7. Make some ACs have strikethrough content: -deprecated text- (JIRA wiki markup for superseded requirements)

Generate the {batch_size} stories now as a JSON array:"""


def call_gateway(prompt: str, max_retries: int = 3) -> dict | None:
    """Make a single API call to the LLM Gateway with retry on disconnect."""
    verify = CERT_PATH if CERT_PATH and os.path.exists(CERT_PATH) else True

    url = f"{BASE_URL}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 8192,
        "temperature": 0.8,
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(max_retries):
        try:
            client = httpx.Client(verify=verify, timeout=300)
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            client.close()

            raw_text = data["content"][0]["text"] if data.get("content") else ""
            usage = data.get("usage", {})

            # Extract JSON from response
            text = raw_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = lines[1:] if lines[0].startswith("```") else lines
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)

            try:
                stories = json.loads(text)
                return {"stories": stories, "usage": usage}
            except json.JSONDecodeError:
                # Try to salvage truncated JSON
                last_complete = text.rfind("},")
                if last_complete > 0:
                    truncated = text[:last_complete + 1] + "\n]"
                    try:
                        stories = json.loads(truncated)
                        return {"stories": stories, "usage": usage}
                    except json.JSONDecodeError:
                        pass
                return None

        except (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ConnectError) as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f" [retry {attempt+1}/{max_retries} in {wait}s: {type(e).__name__}]", end="", flush=True)
                time.sleep(wait)
            else:
                print(f" [FAILED after {max_retries} attempts: {e}]")
                return None
        except Exception as e:
            print(f" [ERROR: {e}]")
            return None


def story_to_markdown(story: dict) -> str:
    """Convert a story dict to the expected markdown format."""
    lines = [
        f"# {story['id']}: {story['summary']}",
        "",
        f"- **Sprint**: {story['sprint']}",
        f"- **Status**: {story['status']}",
        f"- **Type**: {story['type']}",
        f"- **Priority**: {story['priority']}",
        f"- **Resolution**: {story['resolution']}",
        f"- **Assignee**: {story['assignee']}",
        f"- **Reporter**: {story['reporter']}",
        f"- **Components**: {story['components']}",
        f"- **Epic**: {story['epic']}",
        f"- **Story Points**: {story['story_points']}",
        f"- **Labels**: {story['labels']}",
        "",
        "## Description",
        "",
        story.get("description", ""),
        "",
        "## Acceptance Criteria",
        "",
        story.get("acceptance_criteria", ""),
        "",
    ]
    if story.get("solution"):
        lines.extend(["## Solution", "", story["solution"], ""])

    return "\n".join(lines)


def generate_sprint(sprint_info: dict, global_start_id: int, dry_run: bool = False) -> int:
    """Generate all stories for one sprint. Returns the next available ID."""
    sprint_num = sprint_info["sprint"]
    total_stories = sprint_info["stories"]
    phase = sprint_info["phase"]
    focus = sprint_info["focus"]

    sprint_dir = OUTPUT_DIR / f"Sprint {sprint_num}" / "stories"
    sprint_dir.mkdir(parents=True, exist_ok=True)

    batch_size = 8
    current_id = global_start_id

    print(f"\n{'='*50}")
    print(f"  Sprint {sprint_num} ({phase}) — {total_stories} stories")
    print(f"  Focus: {focus}")
    print(f"  IDs: INS-{current_id:04d} to INS-{current_id + total_stories - 1:04d}")
    print(f"{'='*50}")

    # Resume support: count existing files
    existing_files = list(sprint_dir.glob("INS-*.md"))
    generated = len(existing_files)
    if generated > 0:
        print(f"  Resuming: {generated} stories already exist, starting from INS-{current_id + generated:04d}")

    while generated < total_stories:
        remaining = total_stories - generated
        batch = min(batch_size, remaining)
        batch_start = current_id + generated

        if dry_run:
            print(f"  [{generated+1}-{generated+batch}/{total_stories}] Would generate {batch} stories (INS-{batch_start:04d} to INS-{batch_start+batch-1:04d})")
            generated += batch
            continue

        print(f"  [{generated+1}-{generated+batch}/{total_stories}] Generating INS-{batch_start:04d} to INS-{batch_start+batch-1:04d}...", end="", flush=True)

        prompt = build_generation_prompt(sprint_num, phase, focus, batch_start, batch)
        result = call_gateway(prompt)

        if result and result["stories"]:
            stories = result["stories"]
            tokens = result["usage"].get("input_tokens", 0) + result["usage"].get("output_tokens", 0)
            print(f" {len(stories)} stories ({tokens:,} tokens)")

            for story in stories:
                story_id = story.get("id", f"INS-{batch_start:04d}")
                md_content = story_to_markdown(story)
                story_file = sprint_dir / f"{story_id}.md"
                story_file.write_text(md_content, encoding="utf-8")

            generated += len(stories)
        else:
            print(f" ERROR — retrying in 5s...")
            time.sleep(5)
            continue

        time.sleep(1)  # Rate limiting

    return current_id + total_stories


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate synthetic Insurance Claims dataset")
    parser.add_argument("--sprint", type=int, help="Generate only this sprint number")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without calling LLM")
    args = parser.parse_args()

    if not args.dry_run and (not BASE_URL or not API_KEY):
        print("ERROR: Set ANTHROPIC_BEDROCK_BASE_URL and ANTHROPIC_AUTH_TOKEN")
        return 1

    print("\n=== Synthetic Dataset Generator: Insurance Claims ===")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Model: {MODEL}")
    print(f"  Total planned: {sum(s['stories'] for s in SPRINT_PLAN)} stories across {len(SPRINT_PLAN)} sprints")

    if args.sprint:
        sprints = [s for s in SPRINT_PLAN if s["sprint"] == args.sprint]
        if not sprints:
            print(f"ERROR: Sprint {args.sprint} not found")
            return 1
        # Calculate starting ID for this sprint
        start_id = 1
        for s in SPRINT_PLAN:
            if s["sprint"] == args.sprint:
                break
            start_id += s["stories"]
        generate_sprint(sprints[0], start_id, args.dry_run)
    else:
        current_id = 1
        for sprint_info in SPRINT_PLAN:
            current_id = generate_sprint(sprint_info, current_id, args.dry_run)

    print("\n  Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
