You are analyzing JIRA stories from a CRM implementation project. Extract structured business rules from the Acceptance Criteria text. Each AC typically contains Given/When/Then patterns or conditional logic.

For each rule found, provide:
- **story_id**: The story this rule comes from
- **rule_id**: Story ID + sequential number (e.g., PROJ-1234-R1)
- **trigger**: The triggering condition (WHEN/GIVEN clause)
- **conditions**: Array of specific criteria that must be met:
  - **object**: The CRM object/record involved
  - **field**: The specific field being evaluated
  - **operator**: =, !=, IN, NOT IN, >, <, CONTAINS, IS_NULL, IS_NOT_NULL
  - **value**: The expected value
- **action**: What should happen (THEN clause)
- **action_type**: One of: QUERY | DISPLAY | UPDATE | CREATE | DELETE | VALIDATE | NOTIFY | NAVIGATE
- **objects_involved**: All objects referenced in this rule
- **fields_involved**: All fields referenced in this rule

Guidelines:
- Preserve exact field names and values from the AC (e.g., Status = "Active", Type = "Internal")
- If AC references another story, note it but still extract what you can
- Skip stories with empty AC or "as per Description" unless Description has clear rules
- One AC may contain multiple rules — extract each separately
- Include validation rules, display rules, and automation rules

Output ONLY valid JSON:
```json
{
  "rules": [
    {
      "story_id": "PROJ-1234",
      "rule_id": "PROJ-1234-R1",
      "trigger": "User navigates to provider record and clicks Enroll button",
      "conditions": [
        {"object": "Provider", "field": "Status", "operator": "=", "value": "Active"},
        {"object": "Provider", "field": "Enrollment Type", "operator": "!=", "value": "External"}
      ],
      "action": "Create new Enrollment Case with Status = 'New' and auto-populate provider details",
      "action_type": "CREATE",
      "objects_involved": ["Provider", "Enrollment Case"],
      "fields_involved": ["Status", "Enrollment Type"]
    }
  ]
}
```

Here are the stories to analyze:

{{STORIES}}
