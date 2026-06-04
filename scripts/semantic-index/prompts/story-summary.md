You are analyzing JIRA stories from a CRM implementation project. For each story below, produce a structured summary that captures the business intent and key entities.

For each story, provide:
- **id**: The story ID exactly as given
- **summary**: One sentence capturing the BUSINESS intent (not technical implementation). Start with a verb.
- **action_type**: One of: CREATE | MODIFY | DELETE | CONFIGURE | FIX | ENHANCE | REPORT
- **entities**: Structured extraction of what's mentioned:
  - **objects**: CRM objects/records referenced (use business names, not just API names)
  - **fields**: Specific fields mentioned (include both display name and API name if given)
  - **roles**: User roles or personas mentioned
  - **processes**: Business processes or workflows referenced
  - **integrations**: External systems or tools mentioned
- **business_domain**: The business area this belongs to (e.g., "Provider Management", "Contract Lifecycle", "Enrollment")
- **key_criteria**: The most important acceptance criteria in 1-2 bullet points (if AC exists)

Guidelines:
- If AC says "as per Description" or is empty, derive the intent from the Description
- Business names are more important than API names (but include both when available)
- Capture specific field values and conditions (e.g., Status = "Active", Type = "Internal")
- Note any record type distinctions mentioned

Output ONLY valid JSON:
```json
{
  "stories": [
    {
      "id": "PROJ-1234",
      "summary": "Add automated notification when provider enrollment status changes to approved",
      "action_type": "ENHANCE",
      "entities": {
        "objects": ["Provider", "Enrollment Case", "Notification"],
        "fields": ["Enrollment Status", "Notification Type"],
        "roles": ["Enrollment Coordinator"],
        "processes": ["Provider Enrollment", "Status Change Notification"],
        "integrations": ["Email Service"]
      },
      "business_domain": "Provider Enrollment",
      "key_criteria": ["Send email within 1 hour of status change", "Include provider name and effective date"]
    }
  ]
}
```

Here are the stories to analyze:

{{STORIES}}
