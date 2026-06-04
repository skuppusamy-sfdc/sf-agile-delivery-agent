You are analyzing stories from a CRM implementation project. Given the glossary and story summaries below, identify groups of phrases/concepts that mean the SAME THING even when they use completely different words.

For each equivalence group, provide:
- **canonical**: The most precise and commonly-used form of this concept in the project
- **variants**: All alternative phrases found that refer to the same concept:
  - **phrase**: The variant wording
  - **relationship**: synonym | abbreviation | hypernym | informal | role_variant
  - **confidence**: high | medium | low
- **category**: business_process | business_object | role | status | system | location
- **related_stories**: Story IDs where variants were found

What to look for:
- Same process called different things (e.g., "provider onboarding" = "enrollment" = "credentialing intake")
- Same object with multiple names (e.g., "service agreement" = "facility contract" = "MSA")
- Same role described differently (e.g., "Operations Manager" = "Ops Lead" = "OM")
- Same status with different labels
- System names with informal references

Do NOT group:
- Things that are related but not equivalent (parent/child, sequential steps)
- Terms that happen to co-occur but mean different things
- Generic English synonyms that aren't project-specific

Output ONLY valid JSON:
```json
{
  "equivalence_groups": [
    {
      "canonical": "provider onboarding",
      "variants": [
        {"phrase": "enrollment intake", "relationship": "synonym", "confidence": "high"},
        {"phrase": "credentialing process", "relationship": "synonym", "confidence": "medium"}
      ],
      "category": "business_process",
      "related_stories": ["PROJ-1234", "PROJ-2345"]
    }
  ]
}
```

Context (previously extracted glossary):
{{CONTEXT}}

Here are the stories to analyze:

{{STORIES}}
