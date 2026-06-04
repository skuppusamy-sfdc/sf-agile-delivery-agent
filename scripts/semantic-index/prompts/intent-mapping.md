You are analyzing a CRM implementation project. Generate a mapping of natural language questions that team members might ask to the business processes, objects, and stories that answer them.

Think about what each role would ask:
- **Solution Architect**: conflicts, dependencies, coverage gaps, cross-sprint consistency
- **Technical Architect**: impact analysis, call chains, design patterns, integration points
- **Developer**: how does X work, what triggers Y, what fields are involved, edge cases
- **Tester**: what to test, edge cases, regression scope, expected behavior per condition

For each intent, provide:
- **intent_id**: Short kebab-case identifier
- **canonical_question**: The clearest form of this question
- **query_variations**: 3-5 different ways someone might phrase this (natural language variations)
- **business_process**: The business process this maps to
- **relevant_objects**: CRM objects involved in answering this question
- **relevant_stories**: Stories that contain the answer
- **relevant_components**: Technical components (flows, classes, etc.) if identifiable
- **answer_type**: explanation | list | comparison | impact_analysis | process_flow

Guidelines:
- Generate intents that span the actual content in the stories (not hypothetical)
- Include variations that use acronyms, informal language, and role-specific jargon
- Each intent should be answerable from the corpus
- Prioritize questions that are hard to answer with keyword search (semantic gap)

Output ONLY valid JSON:
```json
{
  "intents": [
    {
      "intent_id": "provider-onboarding-flow",
      "canonical_question": "How does the provider onboarding process work end-to-end?",
      "query_variations": [
        "onboarding steps",
        "how do we enroll a new provider",
        "what triggers after enrollment approval",
        "credentialing intake process"
      ],
      "business_process": "Provider Onboarding",
      "relevant_objects": ["Provider", "Enrollment Case", "Credential Record"],
      "relevant_stories": ["PROJ-1234", "PROJ-2345"],
      "relevant_components": ["Onboarding_Flow", "EnrollmentTriggerHandler"],
      "answer_type": "process_flow"
    }
  ]
}
```

Context (previously extracted glossary and summaries):
{{CONTEXT}}

Here are the story summaries to analyze:

{{STORIES}}
