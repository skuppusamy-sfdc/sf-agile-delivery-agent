#!/usr/bin/env python3
"""
Transcript Analyzer — Mine agent transcripts for query patterns and RAG insights.

Parses all .jsonl transcript files and produces a comprehensive report on:
- What users are asking (query extraction and classification)
- Which stories and components are most-queried
- What tools/files the AI used to answer (retrieval patterns)
- Query patterns that may indicate knowledge gaps

Usage:
    python analyze-transcripts.py                                  # default path
    python analyze-transcripts.py --path /custom/transcripts/dir   # custom path
    python analyze-transcripts.py --output report.md               # custom output
    python analyze-transcripts.py --format json                    # JSON output

Zero external dependencies — uses Python stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple

STORY_ID_RE = re.compile(r"PR\d+-\d+")
WORD_RE = re.compile(r"[a-zA-Z]{2,}")
USER_QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)
TIMESTAMP_RE = re.compile(r"<timestamp>(.*?)</timestamp>", re.DOTALL)
FILE_PATH_RE = re.compile(r'(?:knowledge|artifacts|scripts)/[^\s"\'<>]+\.(?:md|html|py|json|yaml)', re.IGNORECASE)
COMPONENT_RE = re.compile(
    r"(?:Account|Contact|Opportunity|Lead|Case|Task|"
    r"Flow|Trigger|ApexClass|ApexTrigger|LWC|Aura|"
    r"HealthcareProvider|HealthcareFacility|"
    r"Clinician|Provider|Client|Facility|Agreement|"
    r"PlatformEvent|BatchJob|ScheduledJob|"
    r"ValidationRule|ProcessBuilder|WorkflowRule)\w*"
)

INTENT_PATTERNS = {
    "story_lookup": [
        re.compile(r"(?:explain|describe|what is|tell me about|understand)\s+(?:story\s+)?PR\d+", re.I),
        re.compile(r"PR\d+-\d+", re.I),
        re.compile(r"(?:story|stories|jira)\s+(?:for|in|about)", re.I),
    ],
    "component_search": [
        re.compile(r"(?:what|which|find|list)\s+(?:component|metadata|object|field|flow|trigger|class)", re.I),
        re.compile(r"(?:component|metadata|trigger|flow|class|object)\s+(?:for|involved|related|used)", re.I),
        re.compile(r"(?:impacted|affected|touched)\s+(?:component|metadata)", re.I),
    ],
    "conflict_detection": [
        re.compile(r"(?:conflict|overlap|clash|collision)", re.I),
        re.compile(r"(?:cross.?sprint|between\s+sprint|sprint.?conflict)", re.I),
        re.compile(r"(?:already.?built|previous.?sprint|existing)", re.I),
    ],
    "test_planning": [
        re.compile(r"(?:test|testing)\s+(?:scenario|case|plan|script|coverage)", re.I),
        re.compile(r"(?:edge\s+case|negative\s+test|regression|UAT)", re.I),
        re.compile(r"(?:AC\s+coverage|acceptance\s+criteria\s+test)", re.I),
    ],
    "solution_design": [
        re.compile(r"(?:technical\s+solution|design|approach|architecture)", re.I),
        re.compile(r"(?:how\s+(?:to|should|would)\s+(?:implement|build|design))", re.I),
        re.compile(r"(?:recommend|suggest|propose)\s+(?:solution|approach|pattern)", re.I),
    ],
    "impact_analysis": [
        re.compile(r"(?:impact|dependency|dependent|downstream|upstream)", re.I),
        re.compile(r"(?:what\s+(?:is|are)\s+(?:affected|impacted|changed))", re.I),
        re.compile(r"(?:regression\s+risk|side\s+effect)", re.I),
    ],
    "knowledge_query": [
        re.compile(r"(?:what\s+is|how\s+does|explain|describe)\s+(?!story|PR\d)", re.I),
        re.compile(r"(?:tell\s+me\s+about|understand|clarify)", re.I),
    ],
    "workspace_tooling": [
        re.compile(r"(?:script|split|parse|index|analyze|corpus|RAG|token|semantic)", re.I),
        re.compile(r"(?:template|workspace|cursor|rule|skill)", re.I),
    ],
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class UserQuery:
    conversation_id: str
    message_index: int
    timestamp: str
    raw_text: str
    clean_text: str
    word_count: int
    story_ids: List[str]
    components: List[str]
    file_paths: List[str]
    intents: List[str]


@dataclass
class ToolCall:
    conversation_id: str
    tool_name: str
    arguments: Dict[str, Any]
    target_path: str


@dataclass
class Conversation:
    conversation_id: str
    file_path: Path
    is_subagent: bool
    user_queries: List[UserQuery] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    assistant_message_count: int = 0
    total_assistant_chars: int = 0
    first_timestamp: str = ""
    last_timestamp: str = ""


# ---------------------------------------------------------------------------
# 1. Parsing
# ---------------------------------------------------------------------------
def _extract_user_text(content_items: List[Dict]) -> Tuple[str, str, str]:
    """Extract clean user query, raw text, and timestamp from message content."""
    raw_parts: List[str] = []
    for item in content_items:
        if item.get("type") == "text":
            raw_parts.append(item.get("text", ""))

    raw_text = "
".join(raw_parts)

    timestamp = ""
    ts_match = TIMESTAMP_RE.search(raw_text)
    if ts_match:
        timestamp = ts_match.group(1).strip()

    uq_match = USER_QUERY_RE.search(raw_text)
    if uq_match:
        clean_text = uq_match.group(1).strip()
    else:
        clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()
        clean_text = re.sub(r"\s+", " ", clean_text)

    return raw_text, clean_text, timestamp


def _extract_tool_calls(content_items: List[Dict], conv_id: str) -> List[ToolCall]:
    """Extract tool call information from assistant message content."""
    calls: List[ToolCall] = []
    for item in content_items:
        if item.get("type") != "tool_use":
            continue
        tool_name = item.get("name", "")
        arguments = item.get("input", {})
        if not isinstance(arguments, dict):
            arguments = {}

        target = ""
        if "path" in arguments:
            target = str(arguments["path"])
        elif "glob_pattern" in arguments:
            target = str(arguments["glob_pattern"])
        elif "pattern" in arguments:
            target = str(arguments["pattern"])
        elif "command" in arguments:
            target = str(arguments["command"])[:120]

        calls.append(ToolCall(
            conversation_id=conv_id,
            tool_name=tool_name,
            arguments=arguments,
            target_path=target,
        ))
    return calls


def _classify_intent(text: str) -> List[str]:
    """Classify user query intent based on pattern matching."""
    matched: List[str] = []
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(text):
                matched.append(intent)
                break
    if not matched:
        matched.append("general")
    return matched


def parse_transcript(jsonl_path: Path, conv_id: str, is_subagent: bool) -> Conversation:
    """Parse a single .jsonl transcript file."""
    conv = Conversation(
        conversation_id=conv_id,
        file_path=jsonl_path,
        is_subagent=is_subagent,
    )

    msg_index = 0
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                role = entry.get("role", "")
                content = entry.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue

                if role == "user":
                    raw_text, clean_text, timestamp = _extract_user_text(content)
                    if not clean_text or len(clean_text) < 3:
                        continue

                    story_ids = STORY_ID_RE.findall(clean_text)
                    components = COMPONENT_RE.findall(clean_text)
                    file_paths = FILE_PATH_RE.findall(raw_text)
                    intents = _classify_intent(clean_text)

                    query = UserQuery(
                        conversation_id=conv_id,
                        message_index=msg_index,
                        timestamp=timestamp,
                        raw_text=raw_text[:2000],
                        clean_text=clean_text,
                        word_count=len(WORD_RE.findall(clean_text)),
                        story_ids=story_ids,
                        components=list(set(components)),
                        file_paths=file_paths,
                        intents=intents,
                    )
                    conv.user_queries.append(query)

                    if timestamp:
                        if not conv.first_timestamp:
                            conv.first_timestamp = timestamp
                        conv.last_timestamp = timestamp

                    msg_index += 1

                elif role == "assistant":
                    conv.assistant_message_count += 1
                    for item in content:
                        if item.get("type") == "text":
                            conv.total_assistant_chars += len(item.get("text", ""))

                    tool_calls = _extract_tool_calls(content, conv_id)
                    conv.tool_calls.extend(tool_calls)

    except OSError as e:
        print(f"  WARNING: Could not read {jsonl_path}: {e}", file=sys.stderr)

    return conv


def load_all_transcripts(transcripts_dir: Path) -> List[Conversation]:
    """Load all transcripts from the directory structure."""
    conversations: List[Conversation] = []

    if not transcripts_dir.exists():
        return conversations

    for conv_dir in sorted(transcripts_dir.iterdir()):
        if not conv_dir.is_dir():
            continue

        conv_id = conv_dir.name
        jsonl_file = conv_dir / f"{conv_id}.jsonl"

        if jsonl_file.exists():
            conv = parse_transcript(jsonl_file, conv_id, is_subagent=False)
            conversations.append(conv)

        subagents_dir = conv_dir / "subagents"
        if subagents_dir.exists():
            for sub_jsonl in sorted(subagents_dir.glob("*.jsonl")):
                sub_id = sub_jsonl.stem
                sub_conv = parse_transcript(sub_jsonl, sub_id, is_subagent=True)
                conversations.append(sub_conv)

    return conversations


# ---------------------------------------------------------------------------
# 2. Analysis Functions
# ---------------------------------------------------------------------------
def analyze_query_volume(conversations: List[Conversation]) -> Dict:
    """Analyze overall query volume and conversation statistics."""
    parent_convs = [c for c in conversations if not c.is_subagent]
    sub_convs = [c for c in conversations if c.is_subagent]

    all_queries = []
    for c in conversations:
        all_queries.extend(c.user_queries)

    parent_queries = []
    for c in parent_convs:
        parent_queries.extend(c.user_queries)

    query_lengths = [q.word_count for q in all_queries]
    response_lengths = [c.total_assistant_chars for c in conversations if c.total_assistant_chars > 0]

    return {
        "total_conversations": len(parent_convs),
        "total_subagents": len(sub_convs),
        "total_user_queries": len(all_queries),
        "parent_user_queries": len(parent_queries),
        "avg_queries_per_conversation": round(mean(len(c.user_queries) for c in parent_convs), 1) if parent_convs else 0,
        "query_word_count": {
            "avg": round(mean(query_lengths), 1) if query_lengths else 0,
            "median": int(median(query_lengths)) if query_lengths else 0,
            "max": max(query_lengths) if query_lengths else 0,
            "min": min(query_lengths) if query_lengths else 0,
        },
        "response_chars": {
            "avg": round(mean(response_lengths)) if response_lengths else 0,
            "median": int(median(response_lengths)) if response_lengths else 0,
        },
        "date_range": {
            "first": min((c.first_timestamp for c in conversations if c.first_timestamp), default=""),
            "last": max((c.last_timestamp for c in conversations if c.last_timestamp), default=""),
        },
    }


def analyze_intents(conversations: List[Conversation]) -> Dict:
    """Classify and count query intents."""
    all_queries = []
    for c in conversations:
        if not c.is_subagent:
            all_queries.extend(c.user_queries)

    intent_counter: Counter = Counter()
    intent_examples: Dict[str, List[str]] = defaultdict(list)

    for q in all_queries:
        for intent in q.intents:
            intent_counter[intent] += 1
            if len(intent_examples[intent]) < 3:
                preview = q.clean_text[:120]
                intent_examples[intent].append(preview)

    total = len(all_queries)
    return {
        "distribution": [
            {
                "intent": intent,
                "count": count,
                "pct": round(count / total * 100, 1) if total else 0,
                "examples": intent_examples.get(intent, []),
            }
            for intent, count in intent_counter.most_common()
        ],
        "total_classified": total,
    }


def analyze_stories_queried(conversations: List[Conversation]) -> Dict:
    """Identify which stories users ask about most."""
    story_counter: Counter = Counter()
    story_queries: Dict[str, List[str]] = defaultdict(list)

    for c in conversations:
        for q in c.user_queries:
            for sid in q.story_ids:
                story_counter[sid] += 1
                if len(story_queries[sid]) < 3:
                    story_queries[sid].append(q.clean_text[:100])

    queries_with_stories = sum(1 for c in conversations for q in c.user_queries if q.story_ids)
    total_queries = sum(len(c.user_queries) for c in conversations)

    return {
        "unique_stories_queried": len(story_counter),
        "queries_mentioning_stories": queries_with_stories,
        "pct_with_story_id": round(queries_with_stories / total_queries * 100, 1) if total_queries else 0,
        "top_stories": [
            {"story_id": sid, "mentions": count, "sample_queries": story_queries.get(sid, [])}
            for sid, count in story_counter.most_common(25)
        ],
    }


def analyze_components_queried(conversations: List[Conversation]) -> Dict:
    """Identify which components users ask about most."""
    comp_counter: Counter = Counter()
    comp_queries: Dict[str, List[str]] = defaultdict(list)

    for c in conversations:
        for q in c.user_queries:
            for comp in q.components:
                comp_counter[comp] += 1
                if len(comp_queries[comp]) < 2:
                    comp_queries[comp].append(q.clean_text[:100])

    return {
        "unique_components_queried": len(comp_counter),
        "top_components": [
            {"component": comp, "mentions": count, "sample_queries": comp_queries.get(comp, [])}
            for comp, count in comp_counter.most_common(20)
        ],
    }


def analyze_tool_usage(conversations: List[Conversation]) -> Dict:
    """Analyze which tools the AI uses to answer queries."""
    tool_counter: Counter = Counter()
    tool_targets: Dict[str, Counter] = defaultdict(Counter)
    read_paths: Counter = Counter()

    for c in conversations:
        for tc in c.tool_calls:
            tool_counter[tc.tool_name] += 1
            if tc.target_path:
                tool_targets[tc.tool_name][tc.target_path] += 1

            if tc.tool_name == "Read" and tc.target_path:
                normalized = tc.target_path
                for prefix in ("knowledge/", "artifacts/", "scripts/"):
                    if prefix in normalized:
                        normalized = normalized[normalized.index(prefix):]
                        break
                read_paths[normalized] += 1

    grep_patterns: Counter = Counter()
    for c in conversations:
        for tc in c.tool_calls:
            if tc.tool_name == "Grep" and "pattern" in tc.arguments:
                grep_patterns[tc.arguments["pattern"]] += 1

    return {
        "tool_usage": [(name, count) for name, count in tool_counter.most_common()],
        "total_tool_calls": sum(tool_counter.values()),
        "top_read_targets": [(path, count) for path, count in read_paths.most_common(20)],
        "top_grep_patterns": [(pat, count) for pat, count in grep_patterns.most_common(15)],
    }


def analyze_knowledge_gaps(conversations: List[Conversation]) -> Dict:
    """Identify queries that may indicate missing or hard-to-find knowledge."""
    short_conversations = []
    for c in conversations:
        if not c.is_subagent and c.user_queries:
            if len(c.user_queries) <= 2 and c.assistant_message_count <= 3:
                for q in c.user_queries:
                    short_conversations.append({
                        "query": q.clean_text[:150],
                        "intents": q.intents,
                        "conversation_id": c.conversation_id,
                    })

    repeated_topics: Counter = Counter()
    for c in conversations:
        for q in c.user_queries:
            words = [w.lower() for w in WORD_RE.findall(q.clean_text) if len(w) > 3]
            bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
            for bg in bigrams:
                repeated_topics[bg] += 1

    high_freq_topics = [(topic, count) for topic, count in repeated_topics.most_common(30) if count >= 2]

    multi_attempt_queries: List[Dict] = []
    for c in conversations:
        if not c.is_subagent and len(c.user_queries) >= 3:
            query_texts = [q.clean_text[:80] for q in c.user_queries[:5]]
            multi_attempt_queries.append({
                "conversation_id": c.conversation_id,
                "query_count": len(c.user_queries),
                "first_queries": query_texts,
            })

    return {
        "short_abandoned_conversations": short_conversations[:15],
        "recurring_topic_bigrams": high_freq_topics,
        "multi_attempt_conversations": sorted(
            multi_attempt_queries, key=lambda x: -x["query_count"]
        )[:10],
    }


def extract_all_queries_list(conversations: List[Conversation]) -> List[Dict]:
    """Build a flat list of all user queries for the appendix."""
    queries: List[Dict] = []
    for c in conversations:
        if c.is_subagent:
            continue
        for q in c.user_queries:
            queries.append({
                "timestamp": q.timestamp,
                "conversation_id": c.conversation_id[:8],
                "query": q.clean_text[:200],
                "intents": ", ".join(q.intents),
                "stories": ", ".join(q.story_ids) if q.story_ids else "",
                "word_count": q.word_count,
            })
    return queries


# ---------------------------------------------------------------------------
# 3. Report Renderer
# ---------------------------------------------------------------------------
def render_report(
    volume: Dict,
    intents: Dict,
    stories: Dict,
    components: Dict,
    tools: Dict,
    gaps: Dict,
    all_queries: List[Dict],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []

    def _h1(t): lines.append(f"# {t}")
    def _h2(t): lines.extend(["", f"## {t}", ""])
    def _h3(t): lines.extend(["", f"### {t}", ""])
    def _p(t): lines.append(t)
    def _blank(): lines.append("")

    _h1("Query Pattern Analysis — Agent Transcripts")
    _p(f"_Auto-generated by `scripts/analyze-transcripts.py` on {now}. Do not hand-edit._")
    _blank()

    # --- Volume ---
    _h2("Overview")
    _p(f"- **Conversations (parent)**: {volume['total_conversations']}")
    _p(f"- **Subagent sessions**: {volume['total_subagents']}")
    _p(f"- **Total user queries**: {volume['total_user_queries']} (parent only: {volume['parent_user_queries']})")
    _p(f"- **Avg queries per conversation**: {volume['avg_queries_per_conversation']}")
    dr = volume.get("date_range", {})
    if dr.get("first"):
        _p(f"- **Date range**: {dr['first']} — {dr['last']}")
    _blank()
    qwc = volume.get("query_word_count", {})
    _p(f"- **Query length**: avg {qwc.get('avg',0)} words, median {qwc.get('median',0)}, max {qwc.get('max',0)}")
    rc = volume.get("response_chars", {})
    _p(f"- **Response size**: avg {rc.get('avg',0):,} chars, median {rc.get('median',0):,} chars")

    # --- Intents ---
    _h2("Query Intent Classification")
    _p("Queries classified by primary intent using pattern matching.")
    _blank()
    _p("| Intent | Count | % | Example |")
    _p("|---|---:|---:|---|")
    for item in intents.get("distribution", []):
        example = item["examples"][0][:80] if item["examples"] else ""
        _p(f"| {item['intent']} | {item['count']} | {item['pct']}% | {example} |")

    # --- Stories ---
    _h2("Most-Queried Stories")
    _p(f"- **Unique stories referenced**: {stories['unique_stories_queried']}")
    _p(f"- **Queries mentioning a story ID**: {stories['queries_mentioning_stories']} ({stories['pct_with_story_id']}%)")
    _blank()
    top_stories = stories.get("top_stories", [])
    if top_stories:
        _p("| Story ID | Mentions | Sample Query |")
        _p("|---|---:|---|")
        for item in top_stories[:20]:
            sample = item["sample_queries"][0][:80] if item["sample_queries"] else ""
            _p(f"| {item['story_id']} | {item['mentions']} | {sample} |")

    # --- Components ---
    _h2("Most-Queried Components")
    top_comp = components.get("top_components", [])
    if top_comp:
        _p("| Component | Mentions | Sample Query |")
        _p("|---|---:|---|")
        for item in top_comp:
            sample = item["sample_queries"][0][:80] if item["sample_queries"] else ""
            _p(f"| {item['component']} | {item['mentions']} | {sample} |")

    # --- Tool Usage ---
    _h2("AI Tool Usage Patterns")
    _p("How the assistant retrieves information to answer queries.")
    _blank()
    _h3("Tool Call Frequency")
    _p(f"- **Total tool calls**: {tools['total_tool_calls']}")
    _blank()
    _p("| Tool | Calls |")
    _p("|---|---:|")
    for name, count in tools.get("tool_usage", []):
        _p(f"| {name} | {count} |")

    top_reads = tools.get("top_read_targets", [])
    if top_reads:
        _h3("Most-Read Files")
        _p("| File Path | Reads |")
        _p("|---|---:|")
        for path, count in top_reads[:15]:
            _p(f"| `{path}` | {count} |")

    top_grep = tools.get("top_grep_patterns", [])
    if top_grep:
        _h3("Most-Searched Patterns (Grep)")
        _p("| Pattern | Searches |")
        _p("|---|---:|")
        for pat, count in top_grep:
            _p(f"| `{pat}` | {count} |")

    # --- Gaps ---
    _h2("Potential Knowledge Gaps")

    recurring = gaps.get("recurring_topic_bigrams", [])
    if recurring:
        _h3("Recurring Topic Bigrams (asked about repeatedly)")
        _p("| Topic | Occurrences |")
        _p("|---|---:|")
        for topic, count in recurring[:20]:
            _p(f"| {topic} | {count} |")

    multi = gaps.get("multi_attempt_conversations", [])
    if multi:
        _h3("Long Conversations (potential difficulty finding answers)")
        _p("| Conversation | Queries | First Queries |")
        _p("|---|---:|---|")
        for item in multi:
            first_q = item["first_queries"][0][:60] if item["first_queries"] else ""
            _p(f"| {item['conversation_id'][:8]}... | {item['query_count']} | {first_q} |")

    abandoned = gaps.get("short_abandoned_conversations", [])
    if abandoned:
        _h3("Short/Abandoned Conversations (potential quick failures)")
        _p("| Query | Intents |")
        _p("|---|---|")
        for item in abandoned[:10]:
            _p(f"| {item['query'][:100]} | {', '.join(item['intents'])} |")

    # --- Appendix: All Queries ---
    _h2("Appendix: All User Queries")
    _p(f"Complete list of {len(all_queries)} user queries from parent conversations.")
    _blank()
    _p("| # | Timestamp | Conv | Query | Intents | Stories |")
    _p("|---:|---|---|---|---|---|")
    for i, q in enumerate(all_queries, 1):
        ts = q["timestamp"][:20] if q["timestamp"] else ""
        _p(f"| {i} | {ts} | {q['conversation_id']} | {q['query'][:80]} | {q['intents']} | {q['stories']} |")

    # --- Recommendations ---
    _h2("Recommendations")
    recs: List[str] = []

    intent_dist = {item["intent"]: item["count"] for item in intents.get("distribution", [])}
    total_q = intents.get("total_classified", 0)

    general_pct = round(intent_dist.get("general", 0) / total_q * 100, 1) if total_q else 0
    if general_pct > 30:
        recs.append(f"**{general_pct}% of queries classified as 'general'** — consider adding more targeted intent patterns or improving the knowledge base's discoverability for these topics.")

    story_pct = stories.get("pct_with_story_id", 0)
    if story_pct > 50:
        recs.append(f"**{story_pct}% of queries reference a specific story ID** — the per-story markdown files are the primary retrieval target. Ensure all stories have rich AC and Solution sections.")

    if recurring:
        top3 = ", ".join(f'"{t}"' for t, _ in recurring[:3])
        recs.append(f"**Recurring topics** ({top3}) indicate frequently-needed knowledge areas. Consider creating dedicated index files or FAQ documents for these.")

    if not recs:
        recs.append("No critical gaps detected in query patterns.")

    for i, rec in enumerate(recs, 1):
        _p(f"{i}. {rec}")

    return "
".join(lines) + "
"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze agent transcripts for query patterns")
    parser.add_argument("--path", help="Path to agent-transcripts directory")
    parser.add_argument("--output", help="Output file path (default: artifacts/analysis/query-patterns.md)")
    parser.add_argument("--format", choices=["md", "json"], default="md", help="Output format")
    args = parser.parse_args()

    if args.path:
        transcripts_dir = Path(args.path)
    else:
        cursor_projects = Path.home() / ".cursor" / "projects"
        if cursor_projects.exists():
            workspace_root = Path(__file__).resolve().parent.parent
            ws_key = re.sub(r"[^a-zA-Z0-9]+", "-", str(workspace_root)).strip("-").lower()

            found = None
            best_match_len = 0
            for pd in sorted(cursor_projects.iterdir(), reverse=True):
                if not pd.is_dir():
                    continue
                at_dir = pd / "agent-transcripts"
                if not at_dir.exists() or not any(at_dir.iterdir()):
                    continue
                pd_key = re.sub(r"[^a-zA-Z0-9]+", "-", pd.name).strip("-").lower()
                common = len(os.path.commonprefix([ws_key, pd_key]))
                if common > best_match_len:
                    best_match_len = common
                    found = at_dir

            if found:
                transcripts_dir = found
            else:
                print("ERROR: No agent-transcripts directory found. Use --path.", file=sys.stderr)
                return 1
        else:
            print("ERROR: No .cursor/projects/ found. Use --path.", file=sys.stderr)
            return 1

    project_root = Path(__file__).resolve().parent.parent
    artifacts_dir = project_root / "artifacts" / "analysis"

    if not transcripts_dir.exists():
        print(f"ERROR: Transcripts directory not found: {transcripts_dir}", file=sys.stderr)
        return 1

    print(f"
=== Transcript Analyzer ===")
    print(f"  Transcripts dir: {transcripts_dir}")

    print("  Loading transcripts...")
    conversations = load_all_transcripts(transcripts_dir)
    parent_count = sum(1 for c in conversations if not c.is_subagent)
    sub_count = sum(1 for c in conversations if c.is_subagent)
    print(f"  Loaded {len(conversations)} conversations ({parent_count} parent, {sub_count} subagent)")

    if not conversations:
        print("  No transcripts found.")
        return 1

    print("  Analyzing query volume...")
    volume = analyze_query_volume(conversations)

    print("  Classifying intents...")
    intents_data = analyze_intents(conversations)

    print("  Analyzing stories queried...")
    stories_data = analyze_stories_queried(conversations)

    print("  Analyzing components queried...")
    components_data = analyze_components_queried(conversations)

    print("  Analyzing tool usage...")
    tools_data = analyze_tool_usage(conversations)

    print("  Detecting knowledge gaps...")
    gaps_data = analyze_knowledge_gaps(conversations)

    print("  Building query list...")
    all_queries = extract_all_queries_list(conversations)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = artifacts_dir / ("query-patterns.json" if args.format == "json" else "query-patterns.md")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        data = {
            "generated": datetime.now().isoformat(),
            "volume": volume,
            "intents": intents_data,
            "stories": stories_data,
            "components": components_data,
            "tools": tools_data,
            "gaps": gaps_data,
            "queries": all_queries,
        }
        out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        report = render_report(volume, intents_data, stories_data, components_data, tools_data, gaps_data, all_queries)
        out_path.write_text(report, encoding="utf-8")

    print(f"
  Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
