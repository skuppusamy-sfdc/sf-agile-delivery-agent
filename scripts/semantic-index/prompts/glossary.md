You are analyzing JIRA stories from a CRM implementation project. Extract every domain-specific term, acronym, abbreviation, and specialized phrase you find in the stories below.

For each term, provide:
- **term**: The abbreviation or short-form as used in the text
- **expansion**: Full expanded form
- **definition**: A one-sentence definition in the context of this project
- **category**: One of: acronym | role | business_object | process | status_value | system | integration | metric
- **related_sf_object**: If this maps to a Salesforce object/field, note it (otherwise null)
- **found_in**: Story IDs where this term was found
- **synonyms**: Other ways this same concept is referred to

Focus especially on:
- Acronyms and abbreviations used by the team
- Role names and personas
- Business objects as users refer to them (not just API names)
- Process names (workflows, approval steps, lifecycle events)
- Status values and what they mean in context
- System names and integrations
- Domain jargon that a new team member would not understand

Do NOT include:
- Generic software terms (API, UI, bug, sprint, etc.)
- Salesforce platform terms (Apex, Flow, LWC, etc.) unless used with project-specific meaning
- Common English words

Output ONLY valid JSON in this exact format:
```json
{
  "terms": [
    {
      "term": "OBR",
      "expansion": "Onboarding Request",
      "definition": "A case record that tracks the steps required to onboard a new provider into the system",
      "category": "business_object",
      "related_sf_object": "Case (RecordType = Onboarding Request)",
      "found_in": ["PROJ-1234"],
      "synonyms": ["Onboarding Case", "OBR Case"]
    }
  ]
}
```

Here are the stories to analyze:

{{STORIES}}
