You are analyzing stories from a CRM implementation project. Identify semantic relationships between stories that would NOT be found by keyword matching or explicit JIRA links.

Relationship types to detect:
- **DEPENDS_ON**: Story B cannot work correctly unless Story A is complete (functional dependency)
- **EXTENDS**: Story B adds capability on top of what Story A built
- **CONFLICTS_WITH**: Story B modifies the same logic/component in a way that may break Story A
- **SAME_PROCESS**: Both stories are different steps in the same end-to-end business process
- **REGRESSION_RISK**: Changes in Story B could cause regressions in Story A's functionality
- **SUPERSEDES**: Story B replaces or makes Story A obsolete

For each link, provide:
- **from_story**: Source story ID
- **to_story**: Target story ID
- **relationship**: One of the types above
- **confidence**: high | medium (only report high and medium — skip low confidence)
- **reason**: One sentence explaining WHY these are related (the non-obvious insight)
- **shared_concepts**: Business concepts/objects/processes they share

Guidelines:
- Only report relationships with HIGH or MEDIUM confidence
- Do NOT report obvious links (same epic, same component in metadata, already linked in JIRA)
- Focus on non-obvious semantic connections a keyword search would miss
- CONFLICTS_WITH is the most valuable — flag these even at medium confidence
- Consider field-level conflicts: two stories updating the same field with different logic

Output ONLY valid JSON:
```json
{
  "links": [
    {
      "from_story": "PROJ-1234",
      "to_story": "PROJ-2345",
      "relationship": "CONFLICTS_WITH",
      "confidence": "high",
      "reason": "Both stories modify the Account Status field with different trigger conditions",
      "shared_concepts": ["Account Status", "status transition", "activation flow"]
    }
  ]
}
```

Here are the story summaries to analyze:

{{STORIES}}
