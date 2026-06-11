# Plan: Conference Paper — Three Framing Options

## Context

Publish a conference paper (ACL/EMNLP/NeurIPS level) with the RAG layer as the main contribution and the SF Agile Delivery Agent as the applied use case. The system has real metrics available: 1,804 stories, 801 glossary terms extracted, measurable before/after retrieval quality.

Three paper framings to generate — user will select the strongest.

---

## Paper Option A: "LLM-at-Build-Time Beats Embedding RAG for Domain-Specific Enterprise Retrieval"

### Core Claim
One-time LLM extraction into structured flat-file indexes outperforms real-time vector similarity search for domain-specific enterprise knowledge retrieval — at lower cost, better accuracy, and zero inference-time LLM dependency.

### Why It's Novel
- Challenges the assumption that semantic search requires embeddings + vector DBs
- Shows that for **closed, domain-specific corpora** (enterprise JIRA, CRM knowledge), pre-computed semantic indexes are superior
- Introduces a new paradigm: "pay once, query forever" vs "pay per query"

### Experiment Design
| Metric | Baseline (keyword/BM25) | Embedding RAG (ada-002/etc.) | **Ours (LLM-at-build-time)** |
|--------|------------------------|------------------------------|------------------------------|
| Retrieval Precision@5 | Measure | Measure | Measure |
| Recall@10 | Measure | Measure | Measure |
| MRR (Mean Reciprocal Rank) | Measure | Measure | Measure |
| Query latency (ms) | ~5ms | ~200ms | ~5ms |
| Per-query cost | $0 | ~$0.001 | $0 |
| Build cost (one-time) | $0 | ~$1 (embedding) | ~$10 (LLM extraction) |
| Handles synonyms? | No | Partially | Yes (explicit mapping) |
| Handles acronyms? | No | Poorly | Yes (glossary) |
| Infrastructure | None | Vector DB | None |

### Paper Structure
1. Abstract
2. Introduction — The problem with RAG in enterprise settings
3. Related Work — RAG, semantic search, knowledge graphs, domain adaptation
4. Method — LLM-at-build-time architecture (6 index types, adapters, schemas)
5. Experimental Setup — 1,804 stories, human-labeled relevance judgments
6. Results — Precision/Recall/MRR comparison across 3 approaches
7. Analysis — When build-time beats query-time (corpus size, domain density, update frequency)
8. Limitations & Future Work
9. Conclusion

### Strengths for Review
- Clear, falsifiable claim with head-to-head comparison
- Practical — enterprises can adopt immediately (no infrastructure)
- Novel architectural pattern not published elsewhere

### Weaknesses / Risks
- Needs a solid baseline (must implement embedding RAG to compare against)
- Reviewers may argue this only works for small, stable corpora
- Need to address "what about updates?" (incremental rebuild story)

---

## Paper Option B: "Zero-Infrastructure Semantic Search via Pre-Computed Domain Indexes"

### Core Claim
Enterprise teams can achieve embedding-quality semantic retrieval using only Python stdlib + flat JSON files — by decomposing "semantic understanding" into discrete, pre-computed index layers (glossary, synonym graph, intent mapping, business rules) that collectively approximate dense retrieval without any infrastructure.

### Why It's Novel
- Reframes semantic search as a **compilation problem**, not a runtime problem
- Shows that semantic capabilities can be "compiled" into lookup tables
- Introduces a formal decomposition: which aspects of "meaning" can be pre-computed?

### Experiment Design
Ablation study — add one index layer at a time, measure retrieval improvement:

| Configuration | Precision@5 | Recall@10 | Infrastructure |
|---------------|------------|-----------|---------------|
| Keyword only (BM25) | X | X | None |
| + Glossary expansion | X+a | X+b | None |
| + Synonym graph | X+c | X+d | None |
| + Intent mapping | X+e | X+f | None |
| + Business rules | X+g | X+h | None |
| + Cross-story links | X+i | X+j | None |
| **Full stack (all 6)** | **X+k** | **X+l** | **None** |
| Embedding RAG (reference) | Y | Z | Vector DB |

### Paper Structure
1. Abstract
2. Introduction — Semantic search shouldn't require infrastructure
3. Related Work — Embeddings, knowledge bases, query expansion, zero-shot retrieval
4. The Compilation Hypothesis — Meaning can be pre-computed for closed corpora
5. Index Architecture — 6 layers, each capturing a different semantic dimension
6. Experimental Setup — Ablation study design, evaluation protocol
7. Results — Per-layer contribution, diminishing returns analysis
8. Discussion — When does this approach converge to embedding quality?
9. Limitations — Open-domain failure modes, update lag
10. Conclusion

### Strengths for Review
- Strong ablation story (each layer's contribution is measurable)
- Novel framing ("semantic compilation")
- Highly practical — no GPU, no vector DB, runs on a laptop
- Clear related work positioning (extends query expansion literature)

### Weaknesses / Risks
- "Zero infrastructure" claim needs careful scoping (LLM is infrastructure at build time)
- May be seen as incremental over query expansion techniques
- Needs to show it works on multiple domains, not just one project

---

## Paper Option C: "Multi-Layer Index Architecture for Agile Delivery Knowledge Management"

### Core Claim
A layered index architecture (glossary → semantic similarity → business rules → intent mapping → cross-story links) produces measurably better retrieval than any single-index approach, with each layer contributing complementary signal — and the full stack approaching embedding RAG quality at zero runtime cost.

### Why It's Novel
- Introduces a **formal taxonomy of semantic dimensions** for enterprise knowledge
- Shows that different "types of meaning" (terminology, equivalence, intent, causality) require different index structures
- Demonstrates composability — layers are independent, additive, and incrementally valuable

### Experiment Design
Layer contribution analysis + cross-layer synergy measurement:

| Query Type | Best Single Layer | Full Stack | Improvement |
|-----------|------------------|-----------|-------------|
| "What is PO?" (terminology) | Glossary | Full | +X% |
| "Stories about offboarding" (synonyms) | Similarity Map | Full | +Y% |
| "What happens when Status = Active?" (rules) | Business Rules | Full | +Z% |
| "How do I test rate changes?" (intent) | Intent Map | Full | +W% |
| "What conflicts with PROJ-1234?" (relationships) | Cross-Story Links | Full | +V% |

Also measure: **synergy** — do layers amplify each other beyond additive improvement?

### Paper Structure
1. Abstract
2. Introduction — Enterprise knowledge is multi-dimensional
3. Related Work — Knowledge graphs, structured search, enterprise QA
4. Semantic Dimensions Framework — Why one index isn't enough
5. Architecture — 6 index types, their extraction prompts, assembly
6. Experimental Setup — Query taxonomy, evaluation protocol
7. Results — Per-layer and cross-layer analysis
8. Case Study — SF Agile Delivery Agent in production (1,804 stories, 4 roles)
9. Generalization — Applicability to other enterprise domains
10. Conclusion

### Strengths for Review
- Rich experimental story (ablation + synergy + case study)
- Novel framework (semantic dimensions taxonomy)
- Practical case study with real users and real data
- Generalizable beyond Salesforce (any enterprise with structured work items)

### Weaknesses / Risks
- Less "punchy" claim than A or B — harder to summarize in one sentence
- Reviewers may want larger-scale validation (multiple projects)
- "Layered indexes" might be seen as engineering contribution vs. scientific

---

## Metrics Generation Plan (Applies to All Three)

### Evaluation Dataset (to be created)
1. **50-100 test queries** covering all semantic dimensions:
   - Terminology lookups ("What is PO?")
   - Synonym-dependent ("stories about provider termination")
   - Rule-based ("when Status changes to Active")
   - Intent-based ("how to test contracting flow")
   - Relationship-based ("what conflicts with this story")
2. **Human relevance judgments**: For each query, label top-20 stories as relevant/not-relevant
3. **Metrics**: Precision@5, Recall@10, MRR, nDCG@10

### Baselines to Implement
1. **BM25 over raw story text** (current `rag-query.py` keyword scoring)
2. **TF-IDF cosine similarity** (current `analyze-rag-effectiveness.py`)
3. **Embedding RAG** (ada-002 or similar over story chunks + cosine retrieval)
4. **Our system** (LLM-at-build-time indexes + BM25 over enriched content)

### What Exists Already
- 1,804 stories processed
- 801 glossary terms extracted (verified quality)
- BM25 scoring implemented (`rag-query.py`)
- TF-IDF evaluation implemented (`analyze-rag-effectiveness.py`)
- Build cost measured: ~$10 for full corpus, ~45 min processing time

### What Needs to Be Built
- Evaluation query set (50-100 queries with human labels)
- Embedding baseline (embed stories, implement cosine retrieval)
- Automated evaluation harness (compute P@5, R@10, MRR, nDCG)
- Remaining semantic indexes (similarity, rules, links, intents — currently only glossary is built)

---

## Recommendation

**Option B ("Zero-Infrastructure Semantic Search")** is strongest for a conference paper because:
1. Clearest novel claim (semantic search without infrastructure)
2. Best ablation story (6 layers, each measurable)
3. Most generalizable framing (not Salesforce-specific)
4. "Compilation hypothesis" is a fresh conceptual contribution

Option A is strongest if you want industry impact (practical, provocative title). Option C is strongest if you want a systems paper (ICSE, CSCW) rather than NLP venue.

---

## Next Steps (after selection)

1. Generate the evaluation query set + relevance labels
2. Build remaining 5 semantic indexes (run all through LLM Gateway)
3. Implement embedding baseline
4. Build evaluation harness
5. Run experiments, generate tables
6. Draft paper (will produce LaTeX)
