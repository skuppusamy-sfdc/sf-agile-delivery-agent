#!/usr/bin/env python3
"""
RAG Effectiveness Analyzer — Cross-reference user queries against the knowledge base.

Combines outputs from analyze-corpus.py, analyze-transcripts.py, and import-usage-csv.py
to measure retrieval quality, identify knowledge gaps, and produce optimization recommendations.

Uses TF-IDF cosine similarity (zero external dependencies) to match user queries
against story content and detect retrieval misses.

Usage:
    python analyze-rag-effectiveness.py                            # full analysis
    python analyze-rag-effectiveness.py --format json              # JSON output
    python analyze-rag-effectiveness.py --output custom-report.md  # custom path
    python analyze-rag-effectiveness.py --top-k 10                 # top-k matches per query

Zero external dependencies — uses Python stdlib only.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional, Set, Tuple

STORY_ID_RE = re.compile(r"PR\d+-\d+")
WORD_RE = re.compile(r"[a-zA-Z]{2,}")
META_RE = re.compile(r"^- \*\*(.+?)\*\*:\s*(.*)$")
HEADING_RE = re.compile(r"^## (.+)$")
TITLE_RE = re.compile(r"^# (.+)$")
ACRONYM_RE = re.compile(r"[A-Z]{2,5}")

STOP_WORDS = frozenset(
    "a about above after again against all am an and any are aren't as at be because "
    "been before being below between both but by can't cannot could couldn't did didn't "
    "do does doesn't doing don't down during each few for from further get got had "
    "hadn't has hasn't have haven't having he he'd he'll he's her here here's hers "
    "herself him himself his how how's if in into is isn't it it's its itself let's "
    "me more most mustn't my myself no nor not of off on once only or other ought our "
    "ours ourselves out over own same shan't she she'd she'll she's should shouldn't "
    "so some such than that that's the their theirs them themselves then there there's "
    "these they they'd they'll they're they've this those through to too under until "
    "up upon us very was wasn't we we'd we'll we're we've were weren't what what's "
    "when when's where where's which while who who's whom why why's will with won't "
    "would wouldn't you you'd you'll you're you've your yours yourself yourselves "
    "also use used using just like new need make sure shall may must can should would "
    "could might able see set get add one two three four five following based update "
    "create field record type user system data value name please note ensure per via "
    "within without however well still already currently include including included "
    "find give tell write check look want know show help read "
    "atlassian browse https http www net com jira wiki org png jpg gif svg "
    "color image border width height style font background padding margin rgba".split()
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class StoryDoc:
    story_id: str
    summary: str
    sprint: str
    components: str
    epic: str
    labels: str
    text: str
    terms: Counter = field(default_factory=Counter)
    word_count: int = 0


@dataclass
class QueryMatch:
    query_text: str
    query_intents: List[str]
    top_matches: List[Tuple[str, str, float]]  # (story_id, summary, similarity)
    best_similarity: float
    query_stories: List[str]
    had_exact_match: bool


# ---------------------------------------------------------------------------
# 1. Load Knowledge Base for TF-IDF
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> List[str]:
    return [w for w in WORD_RE.findall(text.lower()) if w not in STOP_WORDS and len(w) > 2]


def load_story_corpus(sprints_dir: Path) -> List[StoryDoc]:
    """Load all per-story markdown files and tokenize for TF-IDF."""
    docs: List[StoryDoc] = []

    sprint_dirs = sorted(
        d for d in sprints_dir.iterdir()
        if d.is_dir() and "sprint" in d.name.lower()
    )

    for sprint_dir in sprint_dirs:
        stories_dir = sprint_dir / "stories"
        if not stories_dir.exists():
            continue
        for md_file in sorted(stories_dir.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            story_id = ""
            summary = ""
            title_match = TITLE_RE.match(text.split("
")[0]) if text else None
            if title_match:
                title = title_match.group(1)
                id_match = STORY_ID_RE.search(title)
                if id_match:
                    story_id = id_match.group()
                    summary = title[title.index(":") + 1:].strip() if ":" in title else title
            if not story_id:
                id_match = STORY_ID_RE.search(md_file.stem)
                story_id = id_match.group() if id_match else md_file.stem

            meta: Dict[str, str] = {}
            sections: Dict[str, str] = {}
            current_section: Optional[str] = None
            section_lines: List[str] = []

            for line in text.split("
")[1:]:
                meta_match = META_RE.match(line)
                heading_match = HEADING_RE.match(line)
                if meta_match and current_section is None:
                    meta[meta_match.group(1).strip()] = meta_match.group(2).strip()
                elif heading_match:
                    if current_section is not None:
                        sections[current_section] = "
".join(section_lines).strip()
                    current_section = heading_match.group(1).strip()
                    section_lines = []
                elif current_section is not None:
                    section_lines.append(line)
            if current_section is not None:
                sections[current_section] = "
".join(section_lines).strip()

            search_text = f"{story_id} {summary}"
            for sec in ("Description", "Acceptance Criteria", "Solution", "Build Components"):
                if sec in sections:
                    search_text += " " + sections[sec]

            terms = Counter(_tokenize(search_text))

            docs.append(StoryDoc(
                story_id=story_id,
                summary=summary[:200],
                sprint=sprint_dir.name,
                components=meta.get("Components", ""),
                epic=meta.get("Epic", ""),
                labels=meta.get("Labels", ""),
                text=search_text,
                terms=terms,
                word_count=len(WORD_RE.findall(search_text)),
            ))

    return docs


# ---------------------------------------------------------------------------
# 2. TF-IDF Cosine Similarity
# ---------------------------------------------------------------------------
def _build_idf(docs: List[StoryDoc]) -> Dict[str, float]:
    """Compute inverse document frequency for all terms."""
    n = len(docs)
    df: Counter = Counter()
    for doc in docs:
        for term in doc.terms:
            df[term] += 1
    return {term: math.log(n / (1 + freq)) for term, freq in df.items()}


def _cosine_similarity(query_terms: Counter, doc_terms: Counter, idf: Dict[str, float]) -> float:
    """Compute TF-IDF weighted cosine similarity between a query and a document."""
    q_vec: Dict[str, float] = {}
    for term, count in query_terms.items():
        if term in idf:
            q_vec[term] = count * idf[term]

    d_vec: Dict[str, float] = {}
    for term, count in doc_terms.items():
        if term in idf:
            d_vec[term] = count * idf[term]

    if not q_vec or not d_vec:
        return 0.0

    dot = sum(q_vec.get(t, 0) * d_vec.get(t, 0) for t in set(q_vec) | set(d_vec))
    mag_q = math.sqrt(sum(v * v for v in q_vec.values()))
    mag_d = math.sqrt(sum(v * v for v in d_vec.values()))

    if mag_q == 0 or mag_d == 0:
        return 0.0

    return dot / (mag_q * mag_d)


def _load_taxonomy(artifacts_dir: Path) -> Optional[Dict]:
    """Load keyword-taxonomy.json if it exists."""
    tax_path = artifacts_dir / "keyword-taxonomy.json"
    if tax_path.exists():
        try:
            return json.loads(tax_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _expand_query_with_taxonomy(query_text: str, taxonomy: Dict) -> str:
    """
    Expand a query by resolving acronyms and adding object label variants.
    Returns the original query with expansion terms appended.
    """
    expansions: List[str] = []

    acronyms = taxonomy.get("acronyms", {})
    for m in ACRONYM_RE.finditer(query_text):
        token = m.group()
        if token in acronyms:
            exp = acronyms[token].get("expansion")
            if exp:
                expansions.append(exp)

    query_lower = query_text.lower()
    objects = taxonomy.get("objects", {})
    for api_name, info in objects.items():
        label = info.get("label", "").lower()
        api_lower = api_name.lower().replace("__c", "").replace("__e", "").replace("_", " ")
        if label and (label in query_lower or api_lower in query_lower):
            expansions.append(api_name)
            expansions.append(info.get("label", ""))

    if expansions:
        return query_text + " " + " ".join(expansions)
    return query_text


def _taxonomy_boost(
    query_text: str,
    doc: "StoryDoc",
    taxonomy: Dict,
) -> float:
    """
    Compute a small boost based on shared taxonomy terms between query and doc.
    Returns a value between 0.0 and 0.15.
    """
    if not taxonomy:
        return 0.0

    query_lower = query_text.lower()
    doc_text = f"{doc.text} {doc.components} {doc.epic} {doc.labels}".lower()

    shared = 0
    checks = 0

    for acr, info in taxonomy.get("acronyms", {}).items():
        acr_lower = acr.lower()
        if acr_lower in query_lower:
            checks += 1
            exp = (info.get("expansion") or "").lower()
            if acr_lower in doc_text or (exp and exp in doc_text):
                shared += 1

    for proc, info in taxonomy.get("processes", {}).items():
        if proc in query_lower:
            checks += 1
            if proc in doc_text:
                shared += 1

    for bg in taxonomy.get("bigrams", []):
        phrase = bg.get("phrase", "").lower()
        if phrase and phrase in query_lower:
            checks += 1
            if phrase in doc_text:
                shared += 1

    if checks == 0:
        return 0.0
    return min(0.15, (shared / checks) * 0.15)


def find_matches(
    query_text: str,
    docs: List[StoryDoc],
    idf: Dict[str, float],
    top_k: int = 5,
    taxonomy: Optional[Dict] = None,
) -> List[Tuple[str, str, float]]:
    """Find top-k matching stories for a query using TF-IDF cosine similarity,
    optionally boosted by taxonomy term overlap."""
    expanded = query_text
    if taxonomy:
        expanded = _expand_query_with_taxonomy(query_text, taxonomy)

    query_terms = Counter(_tokenize(expanded))
    if not query_terms:
        return []

    scores: List[Tuple[str, str, float]] = []
    for doc in docs:
        sim = _cosine_similarity(query_terms, doc.terms, idf)
        if taxonomy:
            sim += _taxonomy_boost(query_text, doc, taxonomy)
        if sim > 0.01:
            scores.append((doc.story_id, doc.summary, round(sim, 4)))

    scores.sort(key=lambda x: -x[2])
    return scores[:top_k]


# ---------------------------------------------------------------------------
# 3. Load Query Patterns (from analyze-transcripts output)
# ---------------------------------------------------------------------------
def load_query_patterns(artifacts_dir: Path) -> List[Dict]:
    """Load query patterns from the JSON output of analyze-transcripts.py."""
    json_path = artifacts_dir / "query-patterns.json"
    if json_path.exists():
        data = json.loads(json_path.read_text())
        return data.get("queries", [])

    md_path = artifacts_dir / "query-patterns.md"
    if not md_path.exists():
        return []

    queries: List[Dict] = []
    text = md_path.read_text()
    in_appendix = False

    for line in text.split("
"):
        if "## Appendix: All User Queries" in line:
            in_appendix = True
            continue
        if in_appendix and line.startswith("## "):
            break
        if in_appendix and line.startswith("|") and not line.startswith("| #") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6:
                queries.append({
                    "timestamp": parts[2],
                    "conversation_id": parts[3],
                    "query": parts[4],
                    "intents": parts[5],
                    "stories": parts[6] if len(parts) > 6 else "",
                })

    return queries


# ---------------------------------------------------------------------------
# 4. Load Usage Data (from import-usage-csv output)
# ---------------------------------------------------------------------------
def load_usage_data(artifacts_dir: Path) -> Optional[Dict]:
    """Load usage data from the JSON output of import-usage-csv.py."""
    json_path = artifacts_dir / "usage-trends.json"
    if json_path.exists():
        return json.loads(json_path.read_text())
    return None


# ---------------------------------------------------------------------------
# 5. RAG Effectiveness Analysis
# ---------------------------------------------------------------------------
def analyze_retrieval_quality(
    queries: List[Dict],
    docs: List[StoryDoc],
    idf: Dict[str, float],
    top_k: int,
    taxonomy: Optional[Dict] = None,
) -> Tuple[List[QueryMatch], Dict]:
    """Match each user query against the knowledge base and score retrieval quality."""
    matches: List[QueryMatch] = []

    for q in queries:
        query_text = q.get("query", "")
        if not query_text or len(query_text) < 10:
            continue

        intents = [i.strip() for i in q.get("intents", "").split(",") if i.strip()]

        if any(i in ("workspace_tooling",) for i in intents):
            continue

        top_matches = find_matches(query_text, docs, idf, top_k, taxonomy)
        best_sim = top_matches[0][2] if top_matches else 0.0

        query_stories = STORY_ID_RE.findall(query_text)
        had_exact = any(
            sid == m[0] for sid in query_stories for m in top_matches
        ) if query_stories else False

        matches.append(QueryMatch(
            query_text=query_text[:200],
            query_intents=intents,
            top_matches=top_matches,
            best_similarity=best_sim,
            query_stories=query_stories,
            had_exact_match=had_exact,
        ))

    sims = [m.best_similarity for m in matches]
    quality = {
        "total_queries_analyzed": len(matches),
        "avg_best_similarity": round(mean(sims), 4) if sims else 0,
        "median_best_similarity": round(median(sims), 4) if sims else 0,
        "excellent_above_0_5": sum(1 for s in sims if s >= 0.5),
        "good_0_3_to_0_5": sum(1 for s in sims if 0.3 <= s < 0.5),
        "fair_0_1_to_0_3": sum(1 for s in sims if 0.1 <= s < 0.3),
        "poor_below_0_1": sum(1 for s in sims if s < 0.1),
        "no_match": sum(1 for s in sims if s == 0),
        "queries_with_story_ids": sum(1 for m in matches if m.query_stories),
        "exact_matches_found": sum(1 for m in matches if m.had_exact_match),
    }

    return matches, quality


def identify_knowledge_gaps(
    matches: List[QueryMatch],
    docs: List[StoryDoc],
) -> Dict:
    """Identify queries with poor or no matches — potential knowledge gaps."""
    poor_matches = [m for m in matches if m.best_similarity < 0.1 and not m.had_exact_match]

    gap_terms: Counter = Counter()
    for m in poor_matches:
        terms = _tokenize(m.query_text)
        gap_terms.update(terms)

    all_story_components = set()
    for doc in docs:
        for comp in re.split(r"[,;]+", doc.components):
            comp = comp.strip()
            if comp:
                all_story_components.add(comp.lower())

    queried_but_undocumented: List[str] = []
    for term, count in gap_terms.most_common(50):
        if count >= 2 and term not in all_story_components:
            queried_but_undocumented.append(term)

    well_covered_sprints: Counter = Counter()
    poorly_covered_sprints: Counter = Counter()
    for m in matches:
        if m.top_matches:
            sprint = ""
            for doc in docs:
                if doc.story_id == m.top_matches[0][0]:
                    sprint = doc.sprint
                    break
            if sprint:
                if m.best_similarity >= 0.3:
                    well_covered_sprints[sprint] += 1
                else:
                    poorly_covered_sprints[sprint] += 1

    return {
        "total_gaps": len(poor_matches),
        "gap_pct": round(len(poor_matches) / len(matches) * 100, 1) if matches else 0,
        "gap_queries": [
            {"query": m.query_text[:120], "best_sim": m.best_similarity, "intents": m.query_intents}
            for m in poor_matches[:20]
        ],
        "recurring_gap_terms": gap_terms.most_common(20),
        "queried_but_undocumented_terms": queried_but_undocumented[:15],
        "well_covered_sprints": dict(well_covered_sprints.most_common()),
        "poorly_covered_sprints": dict(poorly_covered_sprints.most_common()),
    }


def analyze_component_coverage(
    matches: List[QueryMatch],
    docs: List[StoryDoc],
) -> Dict:
    """Analyze which components are queried vs documented."""
    doc_components: Counter = Counter()
    for doc in docs:
        for comp in re.split(r"[,;]+", doc.components):
            comp = comp.strip()
            if comp:
                doc_components[comp] += 1

    query_components: Counter = Counter()
    for m in matches:
        for term in _tokenize(m.query_text):
            for comp in doc_components:
                if term == comp.lower() or term in comp.lower():
                    query_components[comp] += 1

    over_documented = [(c, cnt) for c, cnt in doc_components.most_common() if cnt >= 20 and query_components.get(c, 0) < 3]
    under_documented = [(c, query_components.get(c, 0)) for c, cnt in doc_components.items() if cnt <= 2 and query_components.get(c, 0) >= 2]

    return {
        "total_documented_components": len(doc_components),
        "top_documented": doc_components.most_common(15),
        "top_queried": query_components.most_common(15),
        "over_documented": over_documented[:10],
        "under_documented": under_documented[:10],
    }


# ---------------------------------------------------------------------------
# 6. Report Renderer
# ---------------------------------------------------------------------------
def render_report(
    quality: Dict,
    gaps: Dict,
    comp_coverage: Dict,
    matches: List[QueryMatch],
    usage_data: Optional[Dict],
    corpus_size: int,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []

    def _h1(t): lines.append(f"# {t}")
    def _h2(t): lines.extend(["", f"## {t}", ""])
    def _h3(t): lines.extend(["", f"### {t}", ""])
    def _p(t): lines.append(t)
    def _blank(): lines.append("")

    _h1("RAG Effectiveness Report")
    _p(f"_Auto-generated by `scripts/analyze-rag-effectiveness.py` on {now}. Do not hand-edit._")
    _blank()

    # --- Executive Summary ---
    _h2("Executive Summary")
    _p(f"- **Knowledge base**: {corpus_size:,} stories indexed")
    _p(f"- **Queries analyzed**: {quality['total_queries_analyzed']}")
    _p(f"- **Average retrieval similarity**: {quality['avg_best_similarity']:.3f}")
    _p(f"- **Knowledge gaps detected**: {gaps['total_gaps']} ({gaps['gap_pct']}% of queries)")
    if usage_data:
        overview = usage_data.get("overview", {})
        _p(f"- **Total token spend**: {overview.get('totals', {}).get('tokens', 0):,} tokens (${overview.get('totals', {}).get('cost', 0):.2f})")

    # --- Retrieval Quality ---
    _h2("Retrieval Quality")
    _p(f"Using TF-IDF cosine similarity to match user queries against {corpus_size} story documents.")
    _blank()

    total = quality["total_queries_analyzed"]
    _p("| Quality Band | Count | % |")
    _p("|---|---:|---:|")
    _p(f"| Excellent (sim >= 0.5) | {quality['excellent_above_0_5']} | {round(quality['excellent_above_0_5']/total*100,1) if total else 0}% |")
    _p(f"| Good (0.3 - 0.5) | {quality['good_0_3_to_0_5']} | {round(quality['good_0_3_to_0_5']/total*100,1) if total else 0}% |")
    _p(f"| Fair (0.1 - 0.3) | {quality['fair_0_1_to_0_3']} | {round(quality['fair_0_1_to_0_3']/total*100,1) if total else 0}% |")
    _p(f"| Poor (< 0.1) | {quality['poor_below_0_1']} | {round(quality['poor_below_0_1']/total*100,1) if total else 0}% |")
    _p(f"| No match | {quality['no_match']} | {round(quality['no_match']/total*100,1) if total else 0}% |")

    _blank()
    _p(f"- Queries that referenced a specific story ID: {quality['queries_with_story_ids']}")
    _p(f"- Of those, exact story found in top-k: {quality['exact_matches_found']}")

    # --- Knowledge Gaps ---
    _h2("Knowledge Gaps")
    _p(f"**{gaps['total_gaps']}** queries ({gaps['gap_pct']}%) had poor or no matches, indicating potential knowledge gaps.")

    gap_queries = gaps.get("gap_queries", [])
    if gap_queries:
        _h3("Queries With No Good Match")
        _p("| Query | Best Sim | Intents |")
        _p("|---|---:|---|")
        for gq in gap_queries:
            _p(f"| {gq['query'][:80]} | {gq['best_sim']:.3f} | {', '.join(gq['intents'])} |")

    gap_terms = gaps.get("recurring_gap_terms", [])
    if gap_terms:
        _h3("Recurring Terms in Unmatched Queries")
        _p("These terms appear frequently in queries that had no good matches — candidates for new knowledge base content.")
        _blank()
        _p("| Term | Occurrences |")
        _p("|---|---:|")
        for term, count in gap_terms[:15]:
            _p(f"| {term} | {count} |")

    undoc = gaps.get("queried_but_undocumented_terms", [])
    if undoc:
        _h3("Queried But Under-Documented Terms")
        _p("Terms users ask about frequently but have little coverage in the knowledge base:")
        _blank()
        for term in undoc[:10]:
            _p(f"- {term}")

    # --- Component Coverage ---
    _h2("Component Coverage Analysis")
    _p(f"- **Components in knowledge base**: {comp_coverage['total_documented_components']}")

    over = comp_coverage.get("over_documented", [])
    if over:
        _h3("Potentially Over-Documented (many stories, few queries)")
        _p("| Component | Stories | Query Matches |")
        _p("|---|---:|---:|")
        for comp, cnt in over:
            _p(f"| {comp} | {cnt} | low |")

    under = comp_coverage.get("under_documented", [])
    if under:
        _h3("Under-Documented (few stories, some queries)")
        _p("| Component | Query Matches |")
        _p("|---|---:|")
        for comp, q_cnt in under:
            _p(f"| {comp} | {q_cnt} |")

    # --- Sample Matches ---
    _h2("Sample Query Matches")
    _p("Top matches for a selection of user queries, showing TF-IDF similarity scores.")
    _blank()

    shown = 0
    for m in matches:
        if m.best_similarity > 0.05 and shown < 15:
            _h3(f"Query: \"{m.query_text[:80]}\"")
            if m.top_matches:
                _p("| Rank | Story | Similarity | Summary |")
                _p("|---:|---|---:|---|")
                for i, (sid, summ, sim) in enumerate(m.top_matches[:5], 1):
                    _p(f"| {i} | {sid} | {sim:.3f} | {summ[:60]} |")
            shown += 1

    # --- Cost vs Effectiveness ---
    if usage_data:
        _h2("Cost vs. Effectiveness")
        overview = usage_data.get("overview", {})
        totals = overview.get("totals", {})
        avgs = overview.get("averages", {})

        _p(f"- **Total cost**: ${totals.get('cost', 0):.2f} over {overview.get('date_range', {}).get('days', 0)} days")
        _p(f"- **Avg tokens/request**: {avgs.get('tokens_per_request', 0):,}")
        _p(f"- **Avg cost/request**: ${avgs.get('cost_per_request', 0):.4f}")
        _blank()

        cache = usage_data.get("cache", {})
        if cache:
            _p(f"- **Cache hit rate**: {cache.get('overall_cache_rate', 0)}%")
            _p(f"- **Tokens saved by cache**: {cache.get('total_cache_read_tokens', 0):,}")

    # --- Recommendations ---
    _h2("Recommendations")
    recs: List[str] = []

    if quality["avg_best_similarity"] < 0.2:
        recs.append(f"**Average retrieval similarity is low ({quality['avg_best_similarity']:.3f}).** The knowledge base content may not align well with how users phrase queries. Consider enriching story descriptions and AC with domain-specific terms users commonly search for.")

    if gaps["gap_pct"] > 30:
        recs.append(f"**{gaps['gap_pct']}% of queries have no good match.** Review the gap queries above and create dedicated knowledge documents for recurring topics.")

    if gap_terms:
        top3 = ", ".join(f'"{t}"' for t, _ in gap_terms[:3])
        recs.append(f"**Recurring gap terms** ({top3}) suggest areas where the knowledge base needs expansion.")

    if quality["no_match"] > 5:
        recs.append(f"**{quality['no_match']} queries returned zero matches.** These may be about topics entirely outside the current knowledge base, or the query phrasing is too different from story content.")

    if usage_data:
        avg_cost = usage_data.get("overview", {}).get("averages", {}).get("cost_per_request", 0)
        if avg_cost > 1.0:
            recs.append(f"**Average cost per request is ${avg_cost:.2f}.** The per-story markdown files should reduce this — ensure the AI is reading individual story files rather than full sprint HTMLs.")

    if not recs:
        recs.append("Knowledge base coverage is reasonable. Continue enriching stories with detailed AC and Solution sections to improve retrieval quality.")

    for i, rec in enumerate(recs, 1):
        _p(f"{i}. {rec}")

    return "
".join(lines) + "
"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze RAG effectiveness by cross-referencing queries against the knowledge base"
    )
    parser.add_argument("--output", help="Output file path (default: artifacts/analysis/rag-effectiveness-report.md)")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="Output format")
    parser.add_argument("--top-k", type=int, default=5, help="Number of matches per query (default: 5)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    sprints_dir = project_root / "knowledge" / "sprints"
    artifacts_dir = project_root / "artifacts" / "analysis"

    if not sprints_dir.exists():
        print(f"ERROR: Sprint directory not found: {sprints_dir}", file=sys.stderr)
        return 1

    print(f"
=== RAG Effectiveness Analyzer ===")

    print("  Loading knowledge base...")
    docs = load_story_corpus(sprints_dir)
    print(f"  Loaded {len(docs)} story documents")

    if not docs:
        print("  No stories found. Run split-sprint-stories.py first.")
        return 1

    print("  Building TF-IDF index...")
    idf = _build_idf(docs)
    print(f"  Vocabulary size: {len(idf)} terms")

    print("  Loading query patterns...")
    queries = load_query_patterns(artifacts_dir)
    print(f"  Loaded {len(queries)} user queries")

    if not queries:
        print("  No query patterns found. Run analyze-transcripts.py first.")
        print("  Generating report with sample queries only...")
        queries = [
            {"query": "clinician onboarding platform event", "intents": "component_search", "stories": ""},
            {"query": "client contracting agreement process", "intents": "knowledge_query", "stories": ""},
            {"query": "facility agreement rate changes", "intents": "knowledge_query", "stories": ""},
            {"query": "approval flow clinician contract", "intents": "component_search", "stories": ""},
            {"query": "offboarding clinician platform event", "intents": "component_search", "stories": ""},
            {"query": "HPF report email scheduling", "intents": "component_search", "stories": ""},
            {"query": "UAT defects testing issues", "intents": "test_planning", "stories": ""},
            {"query": "Agentforce agent configuration", "intents": "knowledge_query", "stories": ""},
        ]

    print("  Loading usage data...")
    usage_data = load_usage_data(artifacts_dir)
    if usage_data:
        print(f"  Loaded usage data ({usage_data.get('overview', {}).get('total_events', 0)} events)")
    else:
        print("  No usage data found (optional — run import-usage-csv.py to include)")

    print("  Loading keyword taxonomy...")
    taxonomy = _load_taxonomy(artifacts_dir)
    if taxonomy:
        tax_stats = taxonomy.get("stats", {})
        print(f"  Loaded taxonomy ({tax_stats.get('total_objects', 0)} objects, {tax_stats.get('total_acronyms', 0)} acronyms, {tax_stats.get('total_bigrams', 0)} bigrams)")
    else:
        print("  No taxonomy found (optional — run analyze-corpus.py to generate)")

    print("  Analyzing retrieval quality...")
    matches, quality = analyze_retrieval_quality(queries, docs, idf, args.top_k, taxonomy)

    print("  Identifying knowledge gaps...")
    gaps = identify_knowledge_gaps(matches, docs)

    print("  Analyzing component coverage...")
    comp_coverage = analyze_component_coverage(matches, docs)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = artifacts_dir / ("rag-effectiveness-report.json" if args.format == "json" else "rag-effectiveness-report.md")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        data = {
            "generated": datetime.now().isoformat(),
            "quality": quality,
            "gaps": gaps,
            "component_coverage": comp_coverage,
            "matches": [
                {
                    "query": m.query_text,
                    "intents": m.query_intents,
                    "best_similarity": m.best_similarity,
                    "top_matches": [{"story_id": s, "summary": su, "similarity": si} for s, su, si in m.top_matches],
                }
                for m in matches
            ],
        }
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        report = render_report(quality, gaps, comp_coverage, matches, usage_data, len(docs))
        out_path.write_text(report, encoding="utf-8")

    print(f"
  Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
