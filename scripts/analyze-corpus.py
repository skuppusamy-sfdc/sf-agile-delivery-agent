#!/usr/bin/env python3
"""
Corpus Analyzer — Profile the JIRA knowledge base for RAG effectiveness.

Parses all per-story markdown files under knowledge/sprints/*/stories/ and
produces a comprehensive report covering content coverage, density, component
frequency, topic extraction, quality scoring, and RAG retrieval surface analysis.

Usage:
    python analyze-corpus.py                                    # all sprints
    python analyze-corpus.py --sprint "Sprint 14"               # single sprint
    python analyze-corpus.py --format json                      # JSON output
    python analyze-corpus.py --output path/to/custom-report.md  # custom path
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev, quantiles
from typing import Any, Dict, List, Optional, Tuple

try:
    from salesforce_taxonomy import (
        build_full_taxonomy,
        build_object_story_index,
        SFDC_STOP_WORDS,
        normalize_term,
        classify_term,
        find_object_references,
    )
    HAS_TAXONOMY = True
except ImportError:
    HAS_TAXONOMY = False

STORY_ID_RE = re.compile(r"PR\d+-\d+")
WORD_RE = re.compile(r"[a-zA-Z]{2,}")
META_RE = re.compile(r"^- \*\*(.+?)\*\*:\s*(.*)$")
HEADING_RE = re.compile(r"^## (.+)$")
TITLE_RE = re.compile(r"^# (.+)$")

TOKEN_MULTIPLIER = 1.3

_BASE_STOP_WORDS = frozenset(
    "a about above after again against all am an and any are aren't as at be because "
    "been before being below between both but by can't cannot could couldn't did didn't "
    "do does doesn't doing don't down during each few for from further get got had "
    "hadn't has hasn't have haven't having he he'd he'll he's her here here's hers "
    "herself him himself his how how's i i'd i'll i'm i've if in into is isn't it "
    "it's its itself let's me more most mustn't my myself no nor not of off on once "
    "only or other ought our ours ourselves out over own same shan't she she'd she'll "
    "she's should shouldn't so some such than that that's the their theirs them "
    "themselves then there there's these they they'd they'll they're they've this "
    "those through to too under until up upon us very was wasn't we we'd we'll we're "
    "we've were weren't what what's when when's where where's which while who who's "
    "whom why why's will with won't would wouldn't you you'd you'll you're you've "
    "your yours yourself yourselves also use used using just like new need make sure "
    "will shall may must can should would could might able see set get add one two "
    "three four five following based update create field record type user system data "
    "value name please note ensure per via within without however well still already "
    "currently include including included".split()
)

STOP_WORDS = _BASE_STOP_WORDS | (SFDC_STOP_WORDS if HAS_TAXONOMY else frozenset())


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class StorySection:
    name: str
    content: str
    word_count: int
    char_count: int
    line_count: int


@dataclass
class ParsedStory:
    file_path: Path
    file_size: int
    story_id: str
    summary: str
    sprint_folder: str
    metadata: Dict[str, str] = field(default_factory=dict)
    sections: Dict[str, StorySection] = field(default_factory=dict)
    total_word_count: int = 0
    estimated_tokens: int = 0
    quality_score: int = 0


# ---------------------------------------------------------------------------
# 1. Parser
# ---------------------------------------------------------------------------
def parse_story_file(path: Path, sprint_folder: str) -> Optional[ParsedStory]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    lines = text.split("
")
    if not lines:
        return None

    story_id = ""
    summary = ""
    title_match = TITLE_RE.match(lines[0])
    if title_match:
        title = title_match.group(1)
        id_match = STORY_ID_RE.search(title)
        if id_match:
            story_id = id_match.group()
            summary = title[title.index(":") + 1:].strip() if ":" in title else title
        else:
            summary = title

    if not story_id:
        id_match = STORY_ID_RE.search(path.stem)
        story_id = id_match.group() if id_match else path.stem

    metadata: Dict[str, str] = {}
    sections: Dict[str, StorySection] = {}
    current_section: Optional[str] = None
    section_lines: List[str] = []

    for line in lines[1:]:
        meta_match = META_RE.match(line)
        heading_match = HEADING_RE.match(line)

        if meta_match and current_section is None:
            metadata[meta_match.group(1).strip()] = meta_match.group(2).strip()
        elif heading_match:
            if current_section is not None:
                content = "
".join(section_lines).strip()
                words = len(WORD_RE.findall(content))
                sections[current_section] = StorySection(
                    name=current_section,
                    content=content,
                    word_count=words,
                    char_count=len(content),
                    line_count=len([l for l in section_lines if l.strip()]),
                )
            current_section = heading_match.group(1).strip()
            section_lines = []
        elif current_section is not None:
            section_lines.append(line)

    if current_section is not None:
        content = "
".join(section_lines).strip()
        words = len(WORD_RE.findall(content))
        sections[current_section] = StorySection(
            name=current_section,
            content=content,
            word_count=words,
            char_count=len(content),
            line_count=len([l for l in section_lines if l.strip()]),
        )

    total_words = len(WORD_RE.findall(text))

    return ParsedStory(
        file_path=path,
        file_size=path.stat().st_size,
        story_id=story_id,
        summary=summary,
        sprint_folder=sprint_folder,
        metadata=metadata,
        sections=sections,
        total_word_count=total_words,
        estimated_tokens=int(total_words * TOKEN_MULTIPLIER),
    )


def load_corpus(base_path: Path, sprint_filter: Optional[str] = None) -> List[ParsedStory]:
    stories: List[ParsedStory] = []
    sprint_dirs = sorted(
        d for d in base_path.iterdir()
        if d.is_dir() and "sprint" in d.name.lower()
    )

    if sprint_filter:
        sprint_dirs = [d for d in sprint_dirs if d.name == sprint_filter]
        if not sprint_dirs:
            print(f"ERROR: Sprint folder '{sprint_filter}' not found.", file=sys.stderr)
            sys.exit(1)

    for sprint_dir in sprint_dirs:
        stories_dir = sprint_dir / "stories"
        if not stories_dir.exists():
            continue
        for md_file in sorted(stories_dir.glob("*.md")):
            parsed = parse_story_file(md_file, sprint_dir.name)
            if parsed:
                stories.append(parsed)

    return stories


# ---------------------------------------------------------------------------
# 2. Coverage Analysis
# ---------------------------------------------------------------------------
TRACKED_SECTIONS = [
    "Description",
    "Acceptance Criteria",
    "Solution",
    "Build Components",
    "Deployment Instructions",
    "Root Cause",
    "Linked Issues",
    "Sub-tasks",
]

TRACKED_META = ["Status", "Type", "Priority", "Assignee", "Reporter", "Components", "Epic", "Story Points"]


def analyze_coverage(stories: List[ParsedStory]) -> Dict:
    total = len(stories)
    if total == 0:
        return {"total": 0, "sections": {}, "metadata": {}, "by_sprint": {}}

    section_stats = {}
    for sec_name in TRACKED_SECTIONS:
        present = [s for s in stories if sec_name in s.sections and s.sections[sec_name].word_count > 3]
        avg_words = mean(s.sections[sec_name].word_count for s in present) if present else 0
        section_stats[sec_name] = {
            "present": len(present),
            "pct": round(len(present) / total * 100, 1),
            "avg_words": round(avg_words),
        }

    meta_stats = {}
    for key in TRACKED_META:
        present = [s for s in stories if s.metadata.get(key, "").strip()]
        meta_stats[key] = {"present": len(present), "pct": round(len(present) / total * 100, 1)}

    by_sprint: Dict[str, Dict] = {}
    sprint_groups = defaultdict(list)
    for s in stories:
        sprint_groups[s.sprint_folder].append(s)

    for sprint, group in sorted(sprint_groups.items()):
        n = len(group)
        has_ac = sum(1 for s in group if "Acceptance Criteria" in s.sections and s.sections["Acceptance Criteria"].word_count > 3)
        has_sol = sum(1 for s in group if "Solution" in s.sections and s.sections["Solution"].word_count > 3)
        by_sprint[sprint] = {
            "stories": n,
            "ac_pct": round(has_ac / n * 100, 1) if n else 0,
            "sol_pct": round(has_sol / n * 100, 1) if n else 0,
        }

    return {"total": total, "sections": section_stats, "metadata": meta_stats, "by_sprint": by_sprint}


# ---------------------------------------------------------------------------
# 3. Density Analysis
# ---------------------------------------------------------------------------
def analyze_density(stories: List[ParsedStory]) -> Dict:
    if not stories:
        return {}

    sizes = [s.file_size for s in stories]
    words = [s.total_word_count for s in stories]
    tokens = [s.estimated_tokens for s in stories]

    def _pctiles(data: List[int]) -> Dict[str, int]:
        if len(data) < 4:
            return {"min": min(data), "max": max(data), "median": int(median(data))}
        q = quantiles(data, n=10)
        return {
            "min": min(data),
            "p10": int(q[0]),
            "p25": int(q[1]),
            "median": int(median(data)),
            "p75": int(q[6]),
            "p90": int(q[8]),
            "max": max(data),
        }

    size_buckets = {
        "sparse_under_500B": sum(1 for s in sizes if s < 500),
        "light_500B_2KB": sum(1 for s in sizes if 500 <= s < 2000),
        "medium_2KB_10KB": sum(1 for s in sizes if 2000 <= s < 10000),
        "rich_10KB_plus": sum(1 for s in sizes if s >= 10000),
    }

    richness_scores = []
    for s in stories:
        ac_w = s.sections.get("Acceptance Criteria", StorySection("", "", 0, 0, 0)).word_count
        sol_w = s.sections.get("Solution", StorySection("", "", 0, 0, 0)).word_count
        desc_w = s.sections.get("Description", StorySection("", "", 0, 0, 0)).word_count
        rich = (ac_w + sol_w + desc_w) / max(s.total_word_count, 1)
        richness_scores.append(round(rich, 2))

    sprint_density: Dict[str, Dict] = {}
    sprint_groups = defaultdict(list)
    for s in stories:
        sprint_groups[s.sprint_folder].append(s)
    for sprint, group in sorted(sprint_groups.items()):
        sprint_density[sprint] = {
            "stories": len(group),
            "total_bytes": sum(s.file_size for s in group),
            "avg_words": round(mean(s.total_word_count for s in group)),
            "avg_tokens": round(mean(s.estimated_tokens for s in group)),
        }

    return {
        "total_bytes": sum(sizes),
        "total_mb": round(sum(sizes) / 1048576, 2),
        "total_words": sum(words),
        "total_tokens": sum(tokens),
        "size_pctiles": _pctiles(sizes),
        "word_pctiles": _pctiles(words),
        "size_buckets": size_buckets,
        "avg_richness": round(mean(richness_scores), 2) if richness_scores else 0,
        "by_sprint": sprint_density,
    }


# ---------------------------------------------------------------------------
# 4. Component Frequency
# ---------------------------------------------------------------------------
def analyze_components(stories: List[ParsedStory], metadata_dir: Path) -> Dict:
    component_stories: Dict[str, List[str]] = defaultdict(list)
    for s in stories:
        raw = s.metadata.get("Components", "").strip()
        if not raw:
            continue
        for comp in re.split(r"[,;]+", raw):
            comp = comp.strip()
            if comp:
                component_stories[comp].append(s.story_id)

    top = sorted(component_stories.items(), key=lambda x: -len(x[1]))
    orphans = [(c, ids) for c, ids in top if len(ids) == 1]

    documented = set()
    if metadata_dir.exists():
        for md_file in metadata_dir.rglob("*.md"):
            documented.add(md_file.stem)

    missing_docs = [c for c, _ in top if c not in documented and c.lower() != "readme"]

    sprint_comp: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in stories:
        raw = s.metadata.get("Components", "").strip()
        if not raw:
            continue
        for comp in re.split(r"[,;]+", raw):
            comp = comp.strip()
            if comp:
                sprint_comp[s.sprint_folder][comp] += 1

    return {
        "total_unique": len(component_stories),
        "top": [(c, len(ids)) for c, ids in top[:20]],
        "orphans": [(c, ids[0]) for c, ids in orphans],
        "missing_metadata_docs": missing_docs[:20],
        "by_sprint": {sp: dict(comps) for sp, comps in sorted(sprint_comp.items())},
    }


# ---------------------------------------------------------------------------
# 4b. Label Frequency
# ---------------------------------------------------------------------------
def analyze_labels(stories: List[ParsedStory]) -> Dict:
    label_stories: Dict[str, List[str]] = defaultdict(list)
    for s in stories:
        raw = s.metadata.get("Labels", "").strip()
        if not raw:
            continue
        for label in re.split(r"[,;]+", raw):
            label = label.strip()
            if label:
                label_stories[label].append(s.story_id)

    top = sorted(label_stories.items(), key=lambda x: -len(x[1]))

    process_labels = []
    environment_labels = []
    for label, sids in top:
        low = label.lower()
        if any(k in low for k in ("uat", "prod", "qa", "smoke", "regression", "test", "hypercare")):
            environment_labels.append((label, len(sids)))
        elif any(k in low for k in ("onboarding", "offboarding", "contracting", "maintenance",
                                     "scheduling", "approval", "migration", "integration",
                                     "client", "provider", "clinician", "facility",
                                     "opportunity", "agreement", "termination")):
            process_labels.append((label, len(sids)))

    sprint_labels: Dict[str, List[Tuple[str, int]]] = {}
    sprint_groups: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in stories:
        raw = s.metadata.get("Labels", "").strip()
        if not raw:
            continue
        for label in re.split(r"[,;]+", raw):
            label = label.strip()
            if label:
                sprint_groups[s.sprint_folder][label] += 1
    for sprint, lbl_counts in sorted(sprint_groups.items()):
        sprint_labels[sprint] = sorted(lbl_counts.items(), key=lambda x: -x[1])[:5]

    has_labels = sum(1 for s in stories if s.metadata.get("Labels", "").strip())

    return {
        "total_unique": len(label_stories),
        "coverage": has_labels,
        "coverage_pct": round(has_labels / len(stories) * 100, 1) if stories else 0,
        "top": [(l, len(ids)) for l, ids in top[:25]],
        "process_labels": process_labels[:15],
        "environment_labels": environment_labels[:15],
        "by_sprint": sprint_labels,
    }


# ---------------------------------------------------------------------------
# 4c. Epic Distribution
# ---------------------------------------------------------------------------
def analyze_epics(stories: List[ParsedStory]) -> Dict:
    epic_stories: Dict[str, List[str]] = defaultdict(list)
    for s in stories:
        raw = s.metadata.get("Epic", "").strip()
        if not raw:
            continue
        epic_stories[raw].append(s.story_id)

    top = sorted(epic_stories.items(), key=lambda x: -len(x[1]))

    epic_sprint: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in stories:
        raw = s.metadata.get("Epic", "").strip()
        if raw:
            epic_sprint[raw][s.sprint_folder] += 1

    epic_quality: Dict[str, float] = {}
    for epic, sids in top[:20]:
        scores = [s.quality_score for s in stories if s.story_id in set(sids)]
        if scores:
            epic_quality[epic] = round(mean(scores), 1)

    has_epic = sum(1 for s in stories if s.metadata.get("Epic", "").strip())

    return {
        "total_unique": len(epic_stories),
        "coverage": has_epic,
        "coverage_pct": round(has_epic / len(stories) * 100, 1) if stories else 0,
        "top": [(e, len(ids)) for e, ids in top[:20]],
        "span": {e: sorted(sprints.keys()) for e, sprints in sorted(epic_sprint.items()) if len(sprints) > 1},
        "quality": epic_quality,
    }


# ---------------------------------------------------------------------------
# 5. Topic Extraction (TF-IDF lite)
# ---------------------------------------------------------------------------
def analyze_topics(stories: List[ParsedStory], taxonomy: Optional[Dict] = None) -> Dict:
    if not stories:
        return {}

    doc_terms: List[Counter] = []
    doc_labels: List[str] = []
    doc_sprints: List[str] = []

    global_raw_counts: Counter = Counter()

    for s in stories:
        text_parts = [s.summary]
        for sec_name in ("Description", "Acceptance Criteria", "Solution"):
            if sec_name in s.sections:
                text_parts.append(s.sections[sec_name].content)
        text = " ".join(text_parts).lower()
        raw_terms = [w for w in WORD_RE.findall(text) if w not in STOP_WORDS and len(w) > 2]
        global_raw_counts.update(raw_terms)
        doc_terms.append(Counter(raw_terms))
        doc_labels.append(s.story_id)
        doc_sprints.append(s.sprint_folder)

    if HAS_TAXONOMY:
        normalized_docs: List[Counter] = []
        for tc in doc_terms:
            normed: Counter = Counter()
            for term, count in tc.items():
                normed[normalize_term(term, global_raw_counts)] += count
            normalized_docs.append(normed)
        doc_terms = normalized_docs

    n_docs = len(doc_terms)
    if n_docs == 0:
        return {}

    df: Counter = Counter()
    for tc in doc_terms:
        for term in tc:
            df[term] += 1

    high_freq_cutoff = n_docs * 0.8
    noise_terms = {t for t, c in df.items() if c > high_freq_cutoff}

    global_tfidf: Counter = Counter()
    for tc in doc_terms:
        for term, count in tc.items():
            if term in noise_terms:
                continue
            idf = math.log(n_docs / (1 + df[term]))
            global_tfidf[term] += count * idf

    top_terms_raw = global_tfidf.most_common(50)

    top_terms_tagged: List[Tuple[str, float, int, str]] = []
    for term, score in top_terms_raw[:30]:
        category = "generic"
        if taxonomy and HAS_TAXONOMY:
            category = classify_term(
                term,
                taxonomy.get("object_dict", {}),
                taxonomy.get("acronyms", {}),
                taxonomy.get("processes", {}),
                taxonomy.get("personas", {}),
                taxonomy.get("integrations", {}),
            )
        top_terms_tagged.append((term, round(score, 1), df[term], category))

    term_to_stories: Dict[str, List[str]] = defaultdict(list)
    for i, tc in enumerate(doc_terms):
        best_term = ""
        best_score = 0
        for term, count in tc.items():
            if term in noise_terms:
                continue
            score = count * math.log(n_docs / (1 + df[term]))
            if score > best_score:
                best_score = score
                best_term = term
        if best_term:
            term_to_stories[best_term].append(doc_labels[i])

    clusters = sorted(
        [(term, len(sids), sids[:5]) for term, sids in term_to_stories.items() if len(sids) >= 3],
        key=lambda x: -x[1],
    )[:15]

    sprint_topics: Dict[str, List[Tuple[str, float]]] = {}
    sprint_groups: Dict[str, List[int]] = defaultdict(list)
    for i, sp in enumerate(doc_sprints):
        sprint_groups[sp].append(i)

    for sprint, indices in sorted(sprint_groups.items()):
        sprint_tfidf: Counter = Counter()
        for idx in indices:
            for term, count in doc_terms[idx].items():
                if term in noise_terms:
                    continue
                sprint_tfidf[term] += count * math.log(n_docs / (1 + df[term]))
        sprint_topics[sprint] = [(t, round(s, 1)) for t, s in sprint_tfidf.most_common(5)]

    return {
        "top_terms": top_terms_tagged,
        "clusters": [(t, c, examples) for t, c, examples in clusters],
        "by_sprint": sprint_topics,
        "noise_terms_removed": len(noise_terms),
    }


# ---------------------------------------------------------------------------
# 6. Quality Scoring
# ---------------------------------------------------------------------------
QUALITY_WEIGHTS = {
    "has_description": 15,
    "has_ac": 25,
    "has_solution": 25,
    "ac_length_100w": 10,
    "sol_length_100w": 10,
    "has_linked": 5,
    "has_components": 5,
    "has_assignee": 5,
}


def score_story(s: ParsedStory) -> int:
    score = 0
    if "Description" in s.sections and s.sections["Description"].word_count > 3:
        score += QUALITY_WEIGHTS["has_description"]
    if "Acceptance Criteria" in s.sections and s.sections["Acceptance Criteria"].word_count > 3:
        score += QUALITY_WEIGHTS["has_ac"]
        if s.sections["Acceptance Criteria"].word_count >= 100:
            score += QUALITY_WEIGHTS["ac_length_100w"]
    if "Solution" in s.sections and s.sections["Solution"].word_count > 3:
        score += QUALITY_WEIGHTS["has_solution"]
        if s.sections["Solution"].word_count >= 100:
            score += QUALITY_WEIGHTS["sol_length_100w"]
    if "Linked Issues" in s.sections and s.sections["Linked Issues"].word_count > 0:
        score += QUALITY_WEIGHTS["has_linked"]
    if s.metadata.get("Components", "").strip():
        score += QUALITY_WEIGHTS["has_components"]
    if s.metadata.get("Assignee", "").strip():
        score += QUALITY_WEIGHTS["has_assignee"]
    return score


def analyze_quality(stories: List[ParsedStory]) -> Dict:
    if not stories:
        return {}

    for s in stories:
        s.quality_score = score_story(s)

    scores = [s.quality_score for s in stories]
    buckets = {
        "0_20": sum(1 for sc in scores if sc <= 20),
        "21_40": sum(1 for sc in scores if 21 <= sc <= 40),
        "41_60": sum(1 for sc in scores if 41 <= sc <= 60),
        "61_80": sum(1 for sc in scores if 61 <= sc <= 80),
        "81_100": sum(1 for sc in scores if 81 <= sc <= 100),
    }

    sorted_stories = sorted(stories, key=lambda s: s.quality_score)
    bottom_20 = [(s.story_id, s.sprint_folder, s.quality_score, s.summary[:60]) for s in sorted_stories[:20]]
    top_20 = [(s.story_id, s.sprint_folder, s.quality_score, s.summary[:60]) for s in sorted_stories[-20:]][::-1]

    sprint_quality: Dict[str, float] = {}
    sprint_groups = defaultdict(list)
    for s in stories:
        sprint_groups[s.sprint_folder].append(s.quality_score)
    for sprint, sc_list in sorted(sprint_groups.items()):
        sprint_quality[sprint] = round(mean(sc_list), 1)

    return {
        "avg": round(mean(scores), 1),
        "median": int(median(scores)),
        "stdev": round(stdev(scores), 1) if len(scores) > 1 else 0,
        "distribution": buckets,
        "bottom_20": bottom_20,
        "top_20": top_20,
        "by_sprint": sprint_quality,
    }


# ---------------------------------------------------------------------------
# 7. RAG Retrieval Surface
# ---------------------------------------------------------------------------
def analyze_retrieval(stories: List[ParsedStory], sprints_dir: Path) -> Dict:
    if not stories:
        return {}

    sizes = [s.file_size for s in stories]
    tokens = [s.estimated_tokens for s in stories]

    single_story = {
        "median_bytes": int(median(sizes)),
        "median_tokens": int(median(tokens)),
        "p75_tokens": int(quantiles(tokens, n=4)[2]) if len(tokens) >= 4 else max(tokens),
    }

    html_sizes = []
    for html_file in sprints_dir.rglob("*.html"):
        html_sizes.append(html_file.stat().st_size)
    html_total = sum(html_sizes)
    html_avg = int(mean(html_sizes)) if html_sizes else 0

    sprint_surface: Dict[str, Dict] = {}
    sprint_groups = defaultdict(list)
    for s in stories:
        sprint_groups[s.sprint_folder].append(s)
    for sprint, group in sorted(sprint_groups.items()):
        total_bytes = sum(s.file_size for s in group)
        total_tokens = sum(s.estimated_tokens for s in group)
        sprint_surface[sprint] = {
            "story_count": len(group),
            "total_bytes": total_bytes,
            "total_tokens": total_tokens,
        }

    comp_surface: Dict[str, Dict] = defaultdict(lambda: {"stories": 0, "total_tokens": 0})
    for s in stories:
        raw = s.metadata.get("Components", "").strip()
        if not raw:
            continue
        for comp in re.split(r"[,;]+", raw):
            comp = comp.strip()
            if comp:
                comp_surface[comp]["stories"] += 1
                comp_surface[comp]["total_tokens"] += s.estimated_tokens

    savings = {
        "old_single_story_avg_tokens": int(html_avg * TOKEN_MULTIPLIER / 4) if html_avg else 0,
        "new_single_story_median_tokens": single_story["median_tokens"],
        "old_html_total_mb": round(html_total / 1048576, 2),
        "new_stories_total_mb": round(sum(sizes) / 1048576, 2),
    }
    if savings["old_single_story_avg_tokens"] > 0:
        savings["reduction_pct"] = round(
            (1 - savings["new_single_story_median_tokens"] / savings["old_single_story_avg_tokens"]) * 100, 1
        )

    return {
        "single_story": single_story,
        "by_sprint": sprint_surface,
        "by_component": {c: dict(v) for c, v in sorted(comp_surface.items(), key=lambda x: -x[1]["stories"])[:15]},
        "html_comparison": savings,
    }


# ---------------------------------------------------------------------------
# 8. Markdown Report Renderer
# ---------------------------------------------------------------------------
def render_report(
    stories: List[ParsedStory],
    coverage: Dict,
    density: Dict,
    components: Dict,
    labels: Dict,
    epics: Dict,
    topics: Dict,
    quality: Dict,
    retrieval: Dict,
    project_name: str,
    taxonomy: Optional[Dict] = None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []

    def _h1(t): lines.append(f"# {t}")
    def _h2(t): lines.extend(["", f"## {t}", ""])
    def _h3(t): lines.extend(["", f"### {t}", ""])
    def _p(t): lines.append(t)
    def _blank(): lines.append("")

    _h1(f"Corpus Profile — {project_name}")
    _p(f"_Auto-generated by `scripts/analyze-corpus.py` on {now}. Do not hand-edit._")
    _blank()

    # --- Summary ---
    _h2("Summary")
    _p(f"- **Total stories**: {coverage['total']}")
    _p(f"- **Sprints**: {len(coverage.get('by_sprint', {}))}")
    _p(f"- **Total size**: {density.get('total_mb', 0)} MB")
    _p(f"- **Total words**: {density.get('total_words', 0):,}")
    _p(f"- **Estimated tokens**: {density.get('total_tokens', 0):,}")

    type_counts = Counter(s.metadata.get("Type", "Unknown") for s in stories)
    _p(f"- **Types**: {', '.join(f'{t} ({c})' for t, c in type_counts.most_common())}")

    status_counts = Counter(s.metadata.get("Status", "Unknown") for s in stories)
    top_statuses = status_counts.most_common(5)
    _p(f"- **Statuses**: {', '.join(f'{t} ({c})' for t, c in top_statuses)}")

    # --- Coverage ---
    _h2("Coverage Analysis")
    _h3("Section Coverage")
    _p("| Section | Present | % | Avg Words |")
    _p("|---|---:|---:|---:|")
    for sec_name in TRACKED_SECTIONS:
        s = coverage["sections"].get(sec_name, {})
        _p(f"| {sec_name} | {s.get('present', 0)} | {s.get('pct', 0)}% | {s.get('avg_words', 0)} |")

    _h3("Metadata Field Coverage")
    _p("| Field | Present | % |")
    _p("|---|---:|---:|")
    for key in TRACKED_META:
        m = coverage["metadata"].get(key, {})
        _p(f"| {key} | {m.get('present', 0)} | {m.get('pct', 0)}% |")

    _h3("Per-Sprint AC and Solution Coverage")
    _p("| Sprint | Stories | AC % | Solution % |")
    _p("|---|---:|---:|---:|")
    for sprint, data in sorted(coverage.get("by_sprint", {}).items()):
        _p(f"| {sprint} | {data['stories']} | {data['ac_pct']}% | {data['sol_pct']}% |")

    # --- Density ---
    _h2("Content Density")
    _h3("File Size Distribution")
    buckets = density.get("size_buckets", {})
    _p(f"- Sparse (<500B): **{buckets.get('sparse_under_500B', 0)}** files")
    _p(f"- Light (500B–2KB): **{buckets.get('light_500B_2KB', 0)}** files")
    _p(f"- Medium (2KB–10KB): **{buckets.get('medium_2KB_10KB', 0)}** files")
    _p(f"- Rich (10KB+): **{buckets.get('rich_10KB_plus', 0)}** files")

    _h3("Percentiles")
    sp = density.get("size_pctiles", {})
    wp = density.get("word_pctiles", {})
    _p("| Metric | Min | P10 | P25 | Median | P75 | P90 | Max |")
    _p("|---|---:|---:|---:|---:|---:|---:|---:|")
    _p(f"| File size (bytes) | {sp.get('min',0)} | {sp.get('p10','-')} | {sp.get('p25','-')} | {sp.get('median',0)} | {sp.get('p75','-')} | {sp.get('p90','-')} | {sp.get('max',0)} |")
    _p(f"| Word count | {wp.get('min',0)} | {wp.get('p10','-')} | {wp.get('p25','-')} | {wp.get('median',0)} | {wp.get('p75','-')} | {wp.get('p90','-')} | {wp.get('max',0)} |")
    _p(f"
- **Average content richness**: {density.get('avg_richness', 0)} (ratio of AC+Solution+Description words to total)")

    _h3("Per-Sprint Density")
    _p("| Sprint | Stories | Total KB | Avg Words | Avg Tokens |")
    _p("|---|---:|---:|---:|---:|")
    for sprint, data in sorted(density.get("by_sprint", {}).items()):
        _p(f"| {sprint} | {data['stories']} | {round(data['total_bytes']/1024, 1)} | {data['avg_words']} | {data['avg_tokens']} |")

    # --- Components ---
    _h2("Component Analysis")
    _h3("Top Components by Story Count")
    _p("| Component | Stories |")
    _p("|---|---:|")
    for comp, count in components.get("top", []):
        _p(f"| {comp} | {count} |")

    orphans = components.get("orphans", [])
    if orphans:
        _h3(f"Orphan Components (appear in 1 story only) — {len(orphans)} total")
        _p("| Component | Story |")
        _p("|---|---|")
        for comp, sid in orphans[:15]:
            _p(f"| {comp} | {sid} |")
        if len(orphans) > 15:
            _p(f"
_…and {len(orphans) - 15} more._")

    missing = components.get("missing_metadata_docs", [])
    if missing:
        _h3("Components Missing from /knowledge/metadata/")
        for comp in missing:
            _p(f"- {comp}")

    # --- Labels ---
    _h2("Label Analysis")
    _p(f"- **Unique labels**: {labels.get('total_unique', 0)}")
    _p(f"- **Stories with labels**: {labels.get('coverage', 0)} ({labels.get('coverage_pct', 0)}%)")

    top_labels = labels.get("top", [])
    if top_labels:
        _h3("Top 25 Labels by Story Count")
        _p("| Label | Stories |")
        _p("|---|---:|")
        for lbl, count in top_labels:
            _p(f"| {lbl} | {count} |")

    proc = labels.get("process_labels", [])
    if proc:
        _h3("Process / Domain Labels")
        _p("| Label | Stories |")
        _p("|---|---:|")
        for lbl, count in proc:
            _p(f"| {lbl} | {count} |")

    env = labels.get("environment_labels", [])
    if env:
        _h3("Environment / Lifecycle Labels")
        _p("| Label | Stories |")
        _p("|---|---:|")
        for lbl, count in env:
            _p(f"| {lbl} | {count} |")

    sprint_labels = labels.get("by_sprint", {})
    if sprint_labels:
        _h3("Per-Sprint Top Labels")
        _p("| Sprint | Top Labels |")
        _p("|---|---|")
        for sprint, lbl_list in sorted(sprint_labels.items()):
            top3 = ", ".join(f"{l} ({c})" for l, c in lbl_list[:3])
            _p(f"| {sprint} | {top3} |")

    # --- Epics ---
    _h2("Epic Analysis")
    _p(f"- **Unique epics**: {epics.get('total_unique', 0)}")
    _p(f"- **Stories with epic**: {epics.get('coverage', 0)} ({epics.get('coverage_pct', 0)}%)")

    top_epics = epics.get("top", [])
    if top_epics:
        _h3("Epics by Story Count")
        _p("| Epic | Stories |")
        _p("|---|---:|")
        for epic, count in top_epics:
            _p(f"| {epic} | {count} |")

    epic_span = epics.get("span", {})
    if epic_span:
        _h3("Multi-Sprint Epics (span across sprints)")
        _p("| Epic | Sprints |")
        _p("|---|---|")
        for epic, sprints_list in sorted(epic_span.items(), key=lambda x: -len(x[1])):
            _p(f"| {epic} | {', '.join(sprints_list)} |")

    epic_quality = epics.get("quality", {})
    if epic_quality:
        _h3("Epic Quality Scores")
        _p("| Epic | Avg Quality |")
        _p("|---|---:|")
        for epic, avg in sorted(epic_quality.items(), key=lambda x: -x[1]):
            _p(f"| {epic} | {avg} |")

    # --- Topics ---
    _h2("Topic Analysis")
    top_terms = topics.get("top_terms", [])
    if top_terms:
        has_category = len(top_terms[0]) >= 4
        if has_category:
            _h3("Top 30 Keywords (by TF-IDF score, with taxonomy category)")
            _p("| Keyword | TF-IDF Score | Stories | Category |")
            _p("|---|---:|---:|---|")
            for item in top_terms:
                term, score, doc_freq = item[0], item[1], item[2]
                cat = item[3] if len(item) > 3 else "generic"
                _p(f"| {term} | {score} | {doc_freq} | {cat} |")
        else:
            _h3("Top 30 Keywords (by TF-IDF score)")
            _p("| Keyword | TF-IDF Score | Appears in N Stories |")
            _p("|---|---:|---:|")
            for term, score, doc_freq in top_terms:
                _p(f"| {term} | {score} | {doc_freq} |")

    clusters = topics.get("clusters", [])
    if clusters:
        _h3("Topic Clusters (stories grouped by dominant keyword)")
        _p("| Dominant Term | Stories | Examples |")
        _p("|---|---:|---|")
        for term, count, examples in clusters:
            _p(f"| {term} | {count} | {', '.join(examples)} |")

    sprint_topics = topics.get("by_sprint", {})
    if sprint_topics:
        _h3("Per-Sprint Top Topics")
        _p("| Sprint | Top Keywords |")
        _p("|---|---|")
        for sprint, terms in sorted(sprint_topics.items()):
            kw = ", ".join(f"{t} ({s})" for t, s in terms[:3])
            _p(f"| {sprint} | {kw} |")

    # --- Quality ---
    _h2("Quality Scores")
    _p(f"- **Average**: {quality.get('avg', 0)} / 100")
    _p(f"- **Median**: {quality.get('median', 0)} / 100")
    _p(f"- **Std Dev**: {quality.get('stdev', 0)}")

    dist = quality.get("distribution", {})
    _h3("Score Distribution")
    _p("| Range | Count |")
    _p("|---|---:|")
    _p(f"| 0–20 | {dist.get('0_20', 0)} |")
    _p(f"| 21–40 | {dist.get('21_40', 0)} |")
    _p(f"| 41–60 | {dist.get('41_60', 0)} |")
    _p(f"| 61–80 | {dist.get('61_80', 0)} |")
    _p(f"| 81–100 | {dist.get('81_100', 0)} |")

    _h3("Per-Sprint Average Quality")
    _p("| Sprint | Avg Score |")
    _p("|---|---:|")
    for sprint, avg in sorted(quality.get("by_sprint", {}).items()):
        _p(f"| {sprint} | {avg} |")

    bottom = quality.get("bottom_20", [])
    if bottom:
        _h3("Bottom 20 Stories (highest-priority gaps)")
        _p("| Story | Sprint | Score | Summary |")
        _p("|---|---|---:|---|")
        for sid, sprint, sc, summ in bottom:
            _p(f"| {sid} | {sprint} | {sc} | {summ} |")

    top = quality.get("top_20", [])
    if top:
        _h3("Top 20 Stories (exemplars)")
        _p("| Story | Sprint | Score | Summary |")
        _p("|---|---|---:|---|")
        for sid, sprint, sc, summ in top:
            _p(f"| {sid} | {sprint} | {sc} | {summ} |")

    # --- Retrieval Surface ---
    _h2("RAG Retrieval Surface")
    single = retrieval.get("single_story", {})
    _h3("Single-Story Lookup Cost")
    _p(f"- Median file size: **{single.get('median_bytes', 0):,}** bytes")
    _p(f"- Median tokens: **{single.get('median_tokens', 0):,}**")
    _p(f"- P75 tokens: **{single.get('p75_tokens', 0):,}**")

    comp_surf = retrieval.get("by_component", {})
    if comp_surf:
        _h3("Component-Wide Search Cost (top components)")
        _p("| Component | Stories | Total Tokens |")
        _p("|---|---:|---:|")
        for comp, data in comp_surf.items():
            _p(f"| {comp} | {data['stories']} | {data['total_tokens']:,} |")

    savings = retrieval.get("html_comparison", {})
    if savings:
        _h3("Old vs New Retrieval Comparison")
        _p(f"- Old approach (full HTML): ~**{savings.get('old_single_story_avg_tokens', 0):,}** tokens per story lookup")
        _p(f"- New approach (per-story MD): ~**{savings.get('new_single_story_median_tokens', 0):,}** tokens per story lookup")
        if "reduction_pct" in savings:
            _p(f"- **Token reduction: {savings['reduction_pct']}%**")
        _p(f"- Old HTML total: {savings.get('old_html_total_mb', 0)} MB across all sprint files")
        _p(f"- New stories total: {savings.get('new_stories_total_mb', 0)} MB across all per-story files")

    sprint_surf = retrieval.get("by_sprint", {})
    if sprint_surf:
        _h3("Per-Sprint Retrieval Cost")
        _p("| Sprint | Stories | Total KB | Total Tokens |")
        _p("|---|---:|---:|---:|")
        for sprint, data in sorted(sprint_surf.items()):
            _p(f"| {sprint} | {data['story_count']} | {round(data['total_bytes']/1024, 1)} | {data['total_tokens']:,} |")

    # --- Keyword Taxonomy ---
    if taxonomy:
        _h2("Keyword Taxonomy (Auto-Detected)")
        stats = taxonomy.get("stats", {})
        _p(f"- **Salesforce objects scanned**: {stats.get('total_objects', 0)}")
        _p(f"- **Objects referenced in stories**: {stats.get('referenced_objects', 0)}")
        _p(f"- **Acronyms detected**: {stats.get('total_acronyms', 0)}")
        _p(f"- **Personas detected**: {stats.get('total_personas', 0)}")
        _p(f"- **Business processes detected**: {stats.get('total_processes', 0)}")
        _p(f"- **Integrations detected**: {stats.get('total_integrations', 0)}")
        _p(f"- **Recurring bigrams**: {stats.get('total_bigrams', 0)}")

        obj_refs = taxonomy.get("object_references", {})
        if obj_refs:
            _h3("Top 30 Referenced Salesforce Objects")
            _p("| Object API Name | Label | Category | Stories | Fields |")
            _p("|---|---|---|---:|---:|")
            for i, (api_name, info) in enumerate(obj_refs.items()):
                if i >= 30:
                    break
                _p(f"| {api_name} | {info['label']} | {info['category']} | {info['story_count']} | {info['field_count']} |")

        acronyms = taxonomy.get("acronyms", {})
        if acronyms:
            _h3("Auto-Detected Acronyms")
            _p("| Acronym | Expansion | Source | Stories |")
            _p("|---|---|---|---:|")
            for acr, info in list(acronyms.items())[:30]:
                exp = info.get("expansion") or "_unresolved_"
                _p(f"| {acr} | {exp} | {info['source']} | {info['story_count']} |")

        personas = taxonomy.get("personas", {})
        if personas:
            _h3("Auto-Detected Personas")
            _p("| Persona | Stories |")
            _p("|---|---:|")
            for persona, info in list(personas.items())[:20]:
                _p(f"| {persona} | {info['story_count']} |")

        processes = taxonomy.get("processes", {})
        if processes:
            _h3("Auto-Detected Business Processes")
            _p("| Process | Source | Stories |")
            _p("|---|---|---:|")
            for proc, info in list(processes.items())[:30]:
                _p(f"| {proc} | {info['source']} | {info['story_count']} |")

        integrations = taxonomy.get("integrations", {})
        if integrations:
            _h3("Auto-Detected Integrations")
            _p("| Integration | Source | Stories |")
            _p("|---|---|---:|")
            for name, info in list(integrations.items())[:15]:
                _p(f"| {name} | {info['source']} | {info['story_count']} |")

        bigrams = taxonomy.get("bigrams", [])
        if bigrams:
            _h3("Top Recurring Bigrams (multi-word terms)")
            _p("| Phrase | Stories |")
            _p("|---|---:|")
            for bg in bigrams[:30]:
                _p(f"| {bg['phrase']} | {bg['story_count']} |")

    # --- Recommendations ---
    _h2("Recommendations")
    recs: List[str] = []

    ac_pct = coverage["sections"].get("Acceptance Criteria", {}).get("pct", 0)
    if ac_pct < 70:
        worst_ac = sorted(coverage.get("by_sprint", {}).items(), key=lambda x: x[1]["ac_pct"])[:3]
        sprints_str = ", ".join(f"{s} ({d['ac_pct']}%)" for s, d in worst_ac)
        recs.append(f"**{round(100 - ac_pct)}% of stories lack Acceptance Criteria.** Lowest coverage sprints: {sprints_str}. Prioritize backfilling AC for these sprints.")

    sol_pct = coverage["sections"].get("Solution", {}).get("pct", 0)
    if sol_pct < 60:
        worst_sol = sorted(coverage.get("by_sprint", {}).items(), key=lambda x: x[1]["sol_pct"])[:3]
        sprints_str = ", ".join(f"{s} ({d['sol_pct']}%)" for s, d in worst_sol)
        recs.append(f"**{round(100 - sol_pct)}% of stories lack a Solution.** Lowest coverage sprints: {sprints_str}.")

    if quality.get("avg", 0) < 60:
        recs.append(f"**Average quality score is {quality['avg']}/100.** Focus on stories scoring below 40 (see Bottom 20 list above).")

    if missing:
        recs.append(f"**{len(missing)} components referenced in stories have no metadata documentation** in `/knowledge/metadata/`. Consider documenting the most-referenced ones first.")

    sparse = density.get("size_buckets", {}).get("sparse_under_500B", 0)
    if sparse > 0:
        recs.append(f"**{sparse} stories are under 500 bytes** (likely just a title with no content). Review and enrich or remove.")

    if not recs:
        recs.append("No critical gaps detected. The knowledge base is well-populated.")

    for i, rec in enumerate(recs, 1):
        _p(f"{i}. {rec}")

    return "
".join(lines) + "
"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Profile the JIRA knowledge base for RAG effectiveness")
    parser.add_argument("--sprint", help="Analyze only this sprint folder (e.g. 'Sprint 14')")
    parser.add_argument("--output", help="Output file path (default: artifacts/analysis/corpus-profile.md)")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="Output format")
    args = parser.parse_args()

    base_path = Path(__file__).resolve().parent.parent / "knowledge" / "sprints"
    metadata_dir = Path(__file__).resolve().parent.parent / "knowledge" / "metadata"
    artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts" / "analysis"

    if not base_path.exists():
        print(f"ERROR: Sprint directory not found: {base_path}", file=sys.stderr)
        return 1

    project_name = "Your Program CnC"

    print(f"
=== Corpus Analyzer — {project_name} ===")
    print(f"Sprints dir: {base_path}")

    stories = load_corpus(base_path, args.sprint)
    if not stories:
        print("No stories found. Run split-sprint-stories.py first.")
        return 1

    print(f"Loaded {len(stories)} stories.")

    print("  Analyzing coverage...")
    coverage = analyze_coverage(stories)

    print("  Analyzing density...")
    density = analyze_density(stories)

    print("  Analyzing components...")
    components = analyze_components(stories, metadata_dir)

    print("  Analyzing labels...")
    labels = analyze_labels(stories)

    taxonomy: Optional[Dict] = None
    if HAS_TAXONOMY:
        print("  Building keyword taxonomy...")
        taxonomy = build_full_taxonomy(metadata_dir, stories)
    else:
        print("  (salesforce_taxonomy module not found — skipping taxonomy)")

    print("  Extracting topics...")
    topics = analyze_topics(stories, taxonomy)

    print("  Scoring quality...")
    quality = analyze_quality(stories)

    print("  Analyzing epics...")
    epics = analyze_epics(stories)

    print("  Analyzing retrieval surface...")
    retrieval = analyze_retrieval(stories, base_path)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = artifacts_dir / ("corpus-profile.json" if args.format == "json" else "corpus-profile.md")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        data = {
            "generated": datetime.now().isoformat(),
            "project": project_name,
            "coverage": coverage,
            "density": density,
            "components": components,
            "labels": labels,
            "epics": epics,
            "topics": topics,
            "quality": quality,
            "retrieval": retrieval,
        }
        if taxonomy:
            data["taxonomy_stats"] = taxonomy.get("stats", {})
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        report = render_report(
            stories, coverage, density, components, labels, epics,
            topics, quality, retrieval, project_name, taxonomy,
        )
        out_path.write_text(report, encoding="utf-8")

    if taxonomy:
        tax_out = artifacts_dir / "keyword-taxonomy.json"
        tax_data = {
            "generated": datetime.now().isoformat(),
            "project": project_name,
            "stats": taxonomy.get("stats", {}),
            "objects": {
                api: {k: v for k, v in info.items() if k not in ("sprints", "stories")}
                for api, info in list(taxonomy.get("object_references", {}).items())[:100]
            },
            "acronyms": taxonomy.get("acronyms", {}),
            "personas": taxonomy.get("personas", {}),
            "processes": {
                k: {kk: vv for kk, vv in v.items()}
                for k, v in list(taxonomy.get("processes", {}).items())[:50]
            },
            "integrations": taxonomy.get("integrations", {}),
            "bigrams": taxonomy.get("bigrams", [])[:50],
        }
        tax_out.parent.mkdir(parents=True, exist_ok=True)
        tax_out.write_text(json.dumps(tax_data, indent=2, default=str), encoding="utf-8")
        print(f"  Wrote {tax_out}")

        obj_index = taxonomy.get("object_story_index")
        if obj_index:
            idx_out = artifacts_dir / "object-story-index.json"
            idx_data = {
                "generated": datetime.now().isoformat(),
                "project": project_name,
                "description": "Cross-lookup: Salesforce objects to JIRA stories. "
                               "Keyed by human-readable label for easy search.",
                "stats": obj_index["stats"],
                "by_label": {
                    label: {
                        k: v for k, v in info.items() if k != "sprints"
                    }
                    for label, info in obj_index["by_label"].items()
                },
                "by_api_name": obj_index["by_api_name"],
            }
            idx_out.write_text(json.dumps(idx_data, indent=2, default=str), encoding="utf-8")
            print(f"  Wrote {idx_out}")

    print(f"
  Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
