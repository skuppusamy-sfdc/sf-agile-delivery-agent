#!/usr/bin/env python3
"""
Salesforce Keyword Taxonomy — Auto-extracting, zero-config, portable.

Builds a comprehensive keyword taxonomy for any Salesforce project by
auto-discovering objects from SFDX metadata, mining acronyms/processes/
personas/integrations from story text, and extracting recurring bigrams.

No hardcoded project vocabulary. Works on any Salesforce project with:
  - SFDX metadata in  knowledge/metadata/**/force-app/main/default/objects/
  - Per-story markdown in knowledge/sprints/*/stories/*.md

Zero external dependencies — Python stdlib only.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Universal constants (same for every Salesforce project)
# ---------------------------------------------------------------------------

SFDC_STOP_WORDS: frozenset = frozenset(
    # URL / HTML / CSS artifacts from JIRA exports
    "atlassian browse https http www net com jira wiki org png jpg gif svg "
    "jpeg bmp webp pdf csv xls xlsx doc docx ppt pptx zip tar "
    "color image border width height style font background padding margin "
    "rgba rgb hex solid none auto inherit transparent inline block flex grid "
    "display visibility overflow cursor pointer opacity transition transform "
    "div span class href src alt title rel target blank "
    "table thead tbody tfoot col colgroup caption "
    # JIRA boilerplate metadata
    "story points sprint assignee reporter resolution closed done "
    "priority medium high low critical blocker created updated resolved "
    "jira confluence attachment thumbnail screenshot "
    # Generic dev terms too common to discriminate
    "field record object page user system data value name list "
    "button click display show hide add remove update create delete edit "
    "save cancel submit select enter view form label input output "
    "component section header footer sidebar panel modal dialog popup "
    "tab menu dropdown checkbox radio toggle switch slider "
    "true false null undefined none empty blank "
    "error warning info debug log trace "
    "test testing tested verify verified check checked "
    "todo fixme hack workaround temporary "
    "api endpoint url uri path route method request response body payload "
    "config configuration setting option parameter argument".split()
)

COMMON_ACRONYM_FALSE_POSITIVES: frozenset = frozenset(
    "AND THE FOR NOT BUT ALL HAS HAD NEW OLD ADD GET SET PUT DEL "
    "ARE WAS HIS HER ITS OUR YOU WHO HOW WHY MAY CAN USE RUN "
    "TRY SAY SAW SEE LET DID END BIG TOP LOW MAX MIN AVG SUM "
    "YES TBD ETA FYI WIP EOD EOW FAQ DIY CEO CTO CFO COO CMO "
    "PDF CSV SQL XML API URL URI SSL TLS SSH FTP DNS CDN JWT "
    "PNG JPG GIF SVG CSS OTP MFA SSO VPN IDE GIT NPM PIP "
    "HTML JSON YAML TOML SOAP REST CRUD SOQL SOSL SFDX MDAPI "
    "TRUE NULL VOID ENUM ELSE ELIF CASE WHEN THEN FROM INTO WITH "
    "LIKE DESC LIMIT OFFSET GROUP ORDER INNER OUTER LEFT RIGHT JOIN "
    "TODO NOTE EDIT COPY MOVE LINK SAVE LOAD OPEN CLOSE SEND WAIT "
    "HTTP "
    # 2-letter tokens that are common English words, not real acronyms
    "OR AN IF IS IT AT BY DO GO IN ME MY NO OF ON SO TO UP WE "
    "AM AS BE HE ID OK US "
    # Common English words sometimes written in ALL CAPS for emphasis
    "ONLY MUST WILL NEED NOTE ALSO EACH BOTH WHEN THEN THAT THIS "
    "SAME TYPE WITH UPON DOES NONE SOME MANY MOST SUCH VERY BEEN "
    "HAVE MAKE GIVE TAKE DONE HERE THEY WHAT WERE ONCE FULL PART ".split()
)

SF_METADATA_TYPES: frozenset = frozenset(
    "apex class trigger flow lwc aura lightning validation rule "
    "permission set profile layout flexipage report dashboard "
    "workflow email template custom metadata platform event "
    "sharing rule record type page object tab app "
    "omniScript omniStudio dataRaptor flexCard integrationProcedure "
    "batch schedulable queueable future invocable".split()
)

CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
ACRONYM_RE = re.compile(r"[A-Z]{2,5}")
AS_A_RE = re.compile(
    r"[Aa]s\s+(?:a|an)\s+([A-Za-z][A-Za-z\s/\-]{2,40}?)(?:\s*[,.]|\s+(?:I|i|we|We)\s)",
)
WORD_RE = re.compile(r"[a-zA-Z]{2,}")
INLINE_EXPANSION_RE = re.compile(
    r"([A-Z]{2,5})\s*\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,6})\)"
    r"|([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,6})\s*\(([A-Z]{2,5})\)"
)
SF_NS = "http://soap.sforce.com/2006/04/metadata"


# ---------------------------------------------------------------------------
# Layer 1: Object Dictionary — auto-extracted from SFDX metadata
# ---------------------------------------------------------------------------

def _split_camel(name: str) -> List[str]:
    """Split CamelCase or underscore-separated name into words."""
    cleaned = name.replace("__c", "").replace("__e", "").replace("__mdt", "").replace("__x", "")
    parts = cleaned.split("__")
    if len(parts) > 1:
        cleaned = parts[-1]
    words = []
    for part in cleaned.split("_"):
        words.extend(CAMEL_RE.sub(" ", part).split())
    return [w for w in words if w]


def _make_initials(words: List[str]) -> str:
    """Generate uppercase initials from a list of words."""
    if len(words) < 2:
        return ""
    return "".join(w[0].upper() for w in words if w)


def _classify_object(api_name: str) -> str:
    """Classify an object by its API name suffix/prefix."""
    if "__e" in api_name:
        return "platform_event"
    if "__mdt" in api_name:
        return "custom_metadata"
    if "__x" in api_name:
        return "external_object"
    if "__c" in api_name:
        parts = api_name.split("__")
        if len(parts) >= 3:
            return "managed_package"
        return "custom_object"
    return "standard_object"


def _extract_namespace(api_name: str) -> Optional[str]:
    """Extract namespace prefix from a managed-package object name."""
    parts = api_name.split("__")
    if len(parts) >= 3:
        return parts[0]
    return None


def _parse_label_from_xml(xml_path: Path) -> Optional[str]:
    """Parse <label> from a .object-meta.xml file."""
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        label_el = root.find(f"{{{SF_NS}}}label")
        if label_el is not None and label_el.text:
            return label_el.text.strip()
    except (ET.ParseError, OSError):
        pass
    return None


def build_object_dictionary(metadata_root: Path) -> Dict[str, Dict[str, Any]]:
    """
    Scan SFDX object directories and build a dictionary of every object.

    Returns {api_name: {label, category, namespace, words, initials, field_count}}.
    """
    obj_dict: Dict[str, Dict[str, Any]] = {}

    object_dirs: List[Path] = []
    for objects_parent in metadata_root.rglob("objects"):
        if objects_parent.is_dir() and "force-app" in str(objects_parent):
            for child in objects_parent.iterdir():
                if child.is_dir():
                    object_dirs.append(child)

    seen_names: Set[str] = set()
    for obj_dir in object_dirs:
        api_name = obj_dir.name
        if api_name in seen_names:
            continue
        seen_names.add(api_name)

        words = _split_camel(api_name)
        initials = _make_initials(words)
        category = _classify_object(api_name)
        namespace = _extract_namespace(api_name)

        xml_file = obj_dir / f"{api_name}.object-meta.xml"
        label = _parse_label_from_xml(xml_file) if xml_file.exists() else None
        if not label:
            label = " ".join(words) if words else api_name

        field_dir = obj_dir / "fields"
        field_count = len(list(field_dir.glob("*.field-meta.xml"))) if field_dir.exists() else 0

        search_variants = set()
        clean_api = api_name.replace("__c", "").replace("__e", "").replace("__mdt", "").replace("__x", "")
        if "__" in clean_api:
            parts = clean_api.split("__")
            clean_api = parts[-1]
        search_variants.add(clean_api.lower())
        search_variants.add(label.lower())
        if "_" in clean_api:
            search_variants.add(clean_api.replace("_", " ").lower())
            search_variants.add(clean_api.replace("_", "").lower())
        if len(words) == 1 and len(words[0]) >= 5:
            search_variants.add(words[0].lower())

        obj_dict[api_name] = {
            "label": label,
            "category": category,
            "namespace": namespace,
            "words": words,
            "initials": initials,
            "field_count": field_count,
            "search_variants": search_variants,
        }

    return obj_dict


# ---------------------------------------------------------------------------
# Layer 2a: Acronym auto-detection
# ---------------------------------------------------------------------------

def auto_detect_acronyms(
    stories: List[Any],
    object_dict: Dict[str, Dict[str, Any]],
    min_stories: int = 3,
) -> Dict[str, Dict[str, Any]]:
    """
    Find uppercase 2-5 char tokens in stories, attempt expansion via object
    initials and inline patterns.
    """
    acronym_stories: Dict[str, Set[str]] = defaultdict(set)
    inline_expansions: Dict[str, str] = {}

    initials_map: Dict[str, List[str]] = defaultdict(list)
    for api_name, info in object_dict.items():
        init = info["initials"]
        if init and len(init) >= 2:
            initials_map[init].append(api_name)

    for story in stories:
        text = _get_story_text(story)
        sid = _get_story_id(story)

        for m in ACRONYM_RE.finditer(text):
            token = m.group()
            if token not in COMMON_ACRONYM_FALSE_POSITIVES:
                acronym_stories[token].add(sid)

        for m in INLINE_EXPANSION_RE.finditer(text):
            if m.group(1) and m.group(2):
                acr, full = m.group(1), m.group(2).strip()
            elif m.group(3) and m.group(4):
                full, acr = m.group(3).strip(), m.group(4)
            else:
                continue
            if acr not in COMMON_ACRONYM_FALSE_POSITIVES and len(full) > 3:
                inline_expansions[acr] = full

    result: Dict[str, Dict[str, Any]] = {}
    for acr, sids in acronym_stories.items():
        if len(sids) < min_stories:
            continue

        expansion = None
        source = "unknown"

        if acr in initials_map:
            candidates = initials_map[acr]
            expansion = object_dict[candidates[0]]["label"]
            source = "object_initials"
        elif acr in inline_expansions:
            candidate = inline_expansions[acr]
            words = candidate.split()
            if len(words) >= 2:
                initials_check = "".join(w[0].upper() for w in words)
                if initials_check.startswith(acr) or acr.startswith(initials_check[:len(acr)]):
                    expansion = candidate
                    source = "inline_text"
                else:
                    expansion = candidate
                    source = "inline_text_unverified"

        result[acr] = {
            "expansion": expansion,
            "source": source,
            "story_count": len(sids),
            "example_stories": sorted(sids)[:5],
        }

    return dict(sorted(result.items(), key=lambda x: -x[1]["story_count"]))


# ---------------------------------------------------------------------------
# Layer 2b: Persona auto-detection
# ---------------------------------------------------------------------------

def auto_detect_personas(stories: List[Any], min_stories: int = 2) -> Dict[str, Dict[str, Any]]:
    """Parse 'As a [ROLE]' from Description sections."""
    persona_stories: Dict[str, Set[str]] = defaultdict(set)

    for story in stories:
        desc = _get_section_text(story, "Description")
        if not desc:
            desc = _get_section_text(story, "Acceptance Criteria")
        if not desc:
            continue

        sid = _get_story_id(story)
        for m in AS_A_RE.finditer(desc):
            role = m.group(1).strip().rstrip(",. ")
            role_lower = role.lower()
            if len(role_lower) < 3 or len(role_lower) > 50:
                continue
            if any(skip in role_lower for skip in ("user who", "person who", "member of")):
                continue
            persona_stories[role_lower].add(sid)

    result: Dict[str, Dict[str, Any]] = {}
    for persona, sids in sorted(persona_stories.items(), key=lambda x: -len(x[1])):
        if len(sids) < min_stories:
            continue
        result[persona] = {
            "story_count": len(sids),
            "example_stories": sorted(sids)[:5],
        }

    return result


# ---------------------------------------------------------------------------
# Layer 2c: Business process auto-detection
# ---------------------------------------------------------------------------

def auto_detect_processes(stories: List[Any], min_stories: int = 3) -> Dict[str, Dict[str, Any]]:
    """
    Mine Epic names, split CamelCase Labels, and extract gerund terms from
    story titles to discover business processes.
    """
    process_stories: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"stories": set(), "source": ""})

    for story in stories:
        sid = _get_story_id(story)

        epic = _get_metadata(story, "Epic")
        if epic:
            key = epic.strip().lower()
            process_stories[key]["stories"].add(sid)
            if not process_stories[key]["source"]:
                process_stories[key]["source"] = "epic"

        labels_raw = _get_metadata(story, "Labels")
        if labels_raw:
            for lbl in re.split(r"[,;]+", labels_raw):
                lbl = lbl.strip()
                if not lbl:
                    continue
                words = CAMEL_RE.sub(" ", lbl).split()
                if len(words) >= 2:
                    key = " ".join(words).lower()
                    process_stories[key]["stories"].add(sid)
                    if not process_stories[key]["source"]:
                        process_stories[key]["source"] = "label"

        summary = _get_summary(story)
        if summary:
            for word in summary.split():
                w = word.strip(",:;()[]\"'").lower()
                if w.endswith("ing") and len(w) >= 5 and w not in (
                    "using", "being", "having", "doing", "getting", "setting",
                    "making", "taking", "giving", "looking", "working", "adding",
                    "following", "including", "existing", "corresponding",
                    "matching", "missing", "nothing", "something", "everything",
                    "anything", "during", "string",
                ):
                    process_stories[w]["stories"].add(sid)
                    if not process_stories[w]["source"]:
                        process_stories[w]["source"] = "title_gerund"

    result: Dict[str, Dict[str, Any]] = {}
    for proc, info in sorted(process_stories.items(), key=lambda x: -len(x[1]["stories"])):
        count = len(info["stories"])
        if count < min_stories:
            continue
        result[proc] = {
            "source": info["source"],
            "story_count": count,
            "example_stories": sorted(info["stories"])[:5],
        }

    return result


# ---------------------------------------------------------------------------
# Layer 2d: Integration auto-detection
# ---------------------------------------------------------------------------

SF_ECOSYSTEM_TERMS: frozenset = frozenset(
    "MuleSoft Heroku PlatformEvent ChangeDataCapture OutboundMessage "
    "RestAPI SoapAPI BulkAPI CompositeAPI StreamingAPI MetadataAPI "
    "ToolingAPI ConnectAPI NamedCredential ExternalService".split()
)

INTEGRATION_CONTEXT_WORDS = frozenset(
    "integration sync api webhook middleware "
    "inbound outbound callout endpoint service "
    "connector adapter bridge etl pipeline".split()
)


def auto_detect_integrations(
    stories: List[Any],
    object_dict: Dict[str, Dict[str, Any]],
    min_stories: int = 2,
) -> Dict[str, Dict[str, Any]]:
    """Detect integrations from namespace prefixes and co-occurrence patterns."""
    integration_stories: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"stories": set(), "source": ""})

    namespaces: Dict[str, str] = {}
    for api_name, info in object_dict.items():
        ns = info.get("namespace")
        if ns:
            namespaces[ns] = api_name

    for ns, example_obj in namespaces.items():
        integration_stories[ns]["source"] = f"namespace:{example_obj}"

    for story in stories:
        text = _get_story_text(story).lower()
        sid = _get_story_id(story)

        for ns in namespaces:
            if ns.lower() in text:
                integration_stories[ns]["stories"].add(sid)

        words = text.split()
        for i, word in enumerate(words):
            if word in INTEGRATION_CONTEXT_WORDS:
                window = words[max(0, i - 5): i + 6]
                for w in window:
                    clean = w.strip(".,;:()[]\"'")
                    if clean and clean[0].isupper() if len(clean) > 0 else False:
                        pass
                    if len(clean) > 2 and clean not in INTEGRATION_CONTEXT_WORDS:
                        for sf_term in SF_ECOSYSTEM_TERMS:
                            if sf_term.lower() == clean:
                                integration_stories[sf_term]["stories"].add(sid)
                                if not integration_stories[sf_term]["source"]:
                                    integration_stories[sf_term]["source"] = "ecosystem_term"

    result: Dict[str, Dict[str, Any]] = {}
    for name, info in sorted(integration_stories.items(), key=lambda x: -len(x[1]["stories"])):
        count = len(info["stories"])
        if count < min_stories:
            continue
        result[name] = {
            "source": info["source"],
            "story_count": count,
            "example_stories": sorted(info["stories"])[:5],
        }

    return result


# ---------------------------------------------------------------------------
# Layer 3: Improved NLP utilities
# ---------------------------------------------------------------------------

def normalize_term(term: str, all_terms: Counter) -> str:
    """Strip trailing 's' if the singular form also exists in the corpus."""
    if term.endswith("s") and len(term) > 3:
        singular = term[:-1]
        if singular in all_terms:
            return singular
    return term


BIGRAM_NOISE = frozenset(
    "smart link expected result actual result reproduce login "
    "sandbox lightning lightning force your-org sandbox "
    "uat bug uat enhancement uat ticket "
    "steps reproduce login corporate ".split()
)


def extract_bigrams(
    stories: List[Any],
    min_stories: int = 5,
    stop_words: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Extract recurring 2-word phrases from story text."""
    if stop_words is None:
        stop_words = set()

    bigram_stories: Dict[str, Set[str]] = defaultdict(set)

    for story in stories:
        sid = _get_story_id(story)
        text_parts = [_get_summary(story)]
        for sec in ("Description", "Acceptance Criteria", "Solution"):
            t = _get_section_text(story, sec)
            if t:
                text_parts.append(t)
        text = " ".join(text_parts).lower()
        words = WORD_RE.findall(text)

        seen_in_doc: Set[str] = set()
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            if w1 in stop_words or w2 in stop_words:
                continue
            if len(w1) <= 2 or len(w2) <= 2:
                continue
            bigram = f"{w1} {w2}"
            if bigram in BIGRAM_NOISE:
                continue
            if bigram not in seen_in_doc:
                seen_in_doc.add(bigram)
                bigram_stories[bigram].add(sid)

    result = []
    for phrase, sids in sorted(bigram_stories.items(), key=lambda x: -len(x[1])):
        if len(sids) < min_stories:
            break
        result.append({
            "phrase": phrase,
            "story_count": len(sids),
            "example_stories": sorted(sids)[:3],
        })

    return result[:100]


def classify_term(
    term: str,
    object_dict: Dict[str, Dict[str, Any]],
    acronyms: Dict[str, Dict[str, Any]],
    processes: Dict[str, Dict[str, Any]],
    personas: Dict[str, Dict[str, Any]],
    integrations: Dict[str, Dict[str, Any]],
) -> str:
    """Return the taxonomy category a term belongs to."""
    term_lower = term.lower()
    term_upper = term.upper()

    if term_upper in acronyms:
        return "acronym"

    for api_name, info in object_dict.items():
        if term_lower in info["search_variants"]:
            return "object"

    if term_lower in processes:
        return "process"

    if term_lower in personas:
        return "persona"

    if term_lower in integrations or term in integrations:
        return "integration"

    return "generic"


# ---------------------------------------------------------------------------
# Object reference analysis
# ---------------------------------------------------------------------------

COMMON_OBJECT_WORDS = frozenset(
    "record action set item type role member status change request "
    "history link collection target lock part failed job batch "
    "user group plan setting score matrix map task event process "
    "template form rule alert message session instance version "
    "log error info result summary detail entry".split()
)


def find_object_references(
    stories: List[Any],
    object_dict: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Cross-reference story text against the object dictionary.

    Uses precise matching: multi-word variants must appear as a phrase,
    single-word variants must be >= 5 chars and not a common filler word.
    """
    obj_stories: Dict[str, Set[str]] = defaultdict(set)

    search_index: Dict[str, List[str]] = defaultdict(list)
    for api_name, info in object_dict.items():
        for variant in info["search_variants"]:
            if " " in variant:
                if len(variant) >= 8:
                    search_index[variant].append(api_name)
            elif len(variant) >= 5 and variant not in COMMON_OBJECT_WORDS:
                search_index[variant].append(api_name)

    for story in stories:
        sid = _get_story_id(story)
        text = _get_story_text(story).lower()
        words_in_text = set(WORD_RE.findall(text))

        for variant, api_names in search_index.items():
            matched = False
            if " " in variant:
                if variant in text:
                    matched = True
            elif variant in words_in_text:
                matched = True

            if matched:
                for api_name in api_names:
                    obj_stories[api_name].add(sid)

    result: Dict[str, Dict[str, Any]] = {}
    for api_name, sids in sorted(obj_stories.items(), key=lambda x: -len(x[1])):
        info = object_dict[api_name]
        result[api_name] = {
            "label": info["label"],
            "category": info["category"],
            "story_count": len(sids),
            "stories": sorted(sids),
            "field_count": info["field_count"],
            "sprints": _count_sprints(stories, sids),
        }

    return result


def build_object_story_index(
    obj_refs: Dict[str, Dict[str, Any]],
    object_dict: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a label-keyed cross-lookup from object references.

    Returns a dict with:
      - "by_label": {label -> {api_name, category, field_count, story_count, stories, sprints}}
      - "by_api_name": {api_name -> label}   (reverse lookup)
      - "stats": summary counts
    """
    by_label: Dict[str, Dict[str, Any]] = {}
    by_api_name: Dict[str, str] = {}

    for api_name, ref_info in obj_refs.items():
        label = ref_info["label"]
        by_api_name[api_name] = label
        entry = {
            "api_name": api_name,
            "category": ref_info["category"],
            "field_count": ref_info["field_count"],
            "story_count": ref_info["story_count"],
            "stories": ref_info.get("stories", []),
            "sprints": ref_info.get("sprints", {}),
        }

        if label in by_label:
            existing = by_label[label]
            if ref_info["story_count"] > existing["story_count"]:
                by_label[label] = entry
        else:
            by_label[label] = entry

    for api_name, info in object_dict.items():
        if api_name not in obj_refs:
            label = info["label"]
            if label not in by_label:
                by_label[label] = {
                    "api_name": api_name,
                    "category": info["category"],
                    "field_count": info["field_count"],
                    "story_count": 0,
                    "stories": [],
                    "sprints": {},
                }
                by_api_name[api_name] = label

    by_label_sorted = dict(
        sorted(by_label.items(), key=lambda x: (-x[1]["story_count"], x[0]))
    )

    referenced = sum(1 for v in by_label_sorted.values() if v["story_count"] > 0)
    return {
        "by_label": by_label_sorted,
        "by_api_name": by_api_name,
        "stats": {
            "total_objects": len(by_label_sorted),
            "objects_with_stories": referenced,
            "objects_without_stories": len(by_label_sorted) - referenced,
            "total_story_links": sum(v["story_count"] for v in by_label_sorted.values()),
        },
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def build_full_taxonomy(
    metadata_root: Path,
    stories: List[Any],
) -> Dict[str, Any]:
    """
    Run all auto-detection engines and return the unified taxonomy.

    This is the main entry point — call with your metadata root and
    parsed story list.
    """
    print("    [taxonomy] Scanning SFDX metadata for objects...")
    object_dict = build_object_dictionary(metadata_root)
    print(f"    [taxonomy] Found {len(object_dict)} objects")

    print("    [taxonomy] Detecting acronyms...")
    acronyms = auto_detect_acronyms(stories, object_dict)
    print(f"    [taxonomy] Found {len(acronyms)} acronyms")

    print("    [taxonomy] Detecting personas...")
    personas = auto_detect_personas(stories)
    print(f"    [taxonomy] Found {len(personas)} personas")

    print("    [taxonomy] Detecting business processes...")
    processes = auto_detect_processes(stories)
    print(f"    [taxonomy] Found {len(processes)} processes")

    print("    [taxonomy] Detecting integrations...")
    integrations = auto_detect_integrations(stories, object_dict)
    print(f"    [taxonomy] Found {len(integrations)} integrations")

    combined_stops = set(SFDC_STOP_WORDS)
    combined_stops.update(
        "a about above after again against all am an and any are as at be because "
        "been before being below between both but by can could did do does doing "
        "don down during each few for from further get got had has have having "
        "he her here hers herself him himself his how if in into is it its itself "
        "let me more most my myself no nor not of off on once only or other our "
        "ours ourselves out over own same she should so some such than that the "
        "their theirs them themselves then there these they this those through to "
        "too under until up upon us very was we were what when where which while "
        "who whom why will with would you your yours yourself yourselves "
        "also use used using just like new need make sure shall may must "
        "following based per via within without however well still already "
        "currently include including included please note ensure".split()
    )

    print("    [taxonomy] Extracting bigrams...")
    bigrams = extract_bigrams(stories, min_stories=5, stop_words=combined_stops)
    print(f"    [taxonomy] Found {len(bigrams)} recurring bigrams")

    print("    [taxonomy] Finding object references in stories...")
    obj_refs = find_object_references(stories, object_dict)
    referenced_count = sum(1 for v in obj_refs.values() if v["story_count"] > 0)
    print(f"    [taxonomy] {referenced_count} objects referenced in stories")

    print("    [taxonomy] Building object-to-story cross-lookup index...")
    object_story_index = build_object_story_index(obj_refs, object_dict)
    print(f"    [taxonomy] Index: {object_story_index['stats']['objects_with_stories']} objects linked to {object_story_index['stats']['total_story_links']} story references")

    return {
        "object_dict": object_dict,
        "object_references": obj_refs,
        "object_story_index": object_story_index,
        "acronyms": acronyms,
        "personas": personas,
        "processes": processes,
        "integrations": integrations,
        "bigrams": bigrams,
        "sfdc_stop_words": sorted(SFDC_STOP_WORDS),
        "stats": {
            "total_objects": len(object_dict),
            "referenced_objects": referenced_count,
            "unreferenced_objects": len(object_dict) - referenced_count,
            "total_acronyms": len(acronyms),
            "total_personas": len(personas),
            "total_processes": len(processes),
            "total_integrations": len(integrations),
            "total_bigrams": len(bigrams),
        },
    }


# ---------------------------------------------------------------------------
# Story accessor helpers (work with both ParsedStory dataclass and dicts)
# ---------------------------------------------------------------------------

def _get_story_id(story: Any) -> str:
    if hasattr(story, "story_id"):
        return story.story_id
    return story.get("story_id", "")


def _get_summary(story: Any) -> str:
    if hasattr(story, "summary"):
        return story.summary
    return story.get("summary", "")


def _get_metadata(story: Any, key: str) -> str:
    if hasattr(story, "metadata"):
        return story.metadata.get(key, "")
    meta = story.get("metadata", {})
    return meta.get(key, "") if isinstance(meta, dict) else ""


def _get_section_text(story: Any, section_name: str) -> str:
    if hasattr(story, "sections"):
        sec = story.sections.get(section_name)
        if sec is None:
            return ""
        return sec.content if hasattr(sec, "content") else str(sec)
    sections = story.get("sections", {})
    sec = sections.get(section_name)
    if sec is None:
        return ""
    return sec.get("content", str(sec)) if isinstance(sec, dict) else str(sec)


def _get_sprint(story: Any) -> str:
    if hasattr(story, "sprint_folder"):
        return story.sprint_folder
    return story.get("sprint_folder", story.get("sprint", ""))


def _get_story_text(story: Any) -> str:
    """Concatenate summary + key sections for full-text search."""
    parts = [_get_summary(story)]
    for sec in ("Description", "Acceptance Criteria", "Solution", "Build Components"):
        t = _get_section_text(story, sec)
        if t:
            parts.append(t)
    meta_fields = ["Components", "Epic", "Labels"]
    for mf in meta_fields:
        v = _get_metadata(story, mf)
        if v:
            parts.append(v)
    return " ".join(parts)


def _count_sprints(stories: List[Any], sids: Set[str]) -> Dict[str, int]:
    """Count how many matching stories fall into each sprint."""
    sprint_counts: Counter = Counter()
    for story in stories:
        if _get_story_id(story) in sids:
            sprint_counts[_get_sprint(story)] += 1
    return dict(sprint_counts.most_common())
