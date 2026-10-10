"""AI #1: LLM parse fallback when rules confidence is low (plan §5.1).

Flow: rules parse → if confidence < threshold (or thin dictionary skills) →
PII mask via ai_gateway → structured JSON → dictionary + in-text skill filter.
Soft-fails to rules.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from worker.ai_flags import feature_on
from worker.ai_gateway import complete_json
from worker.cv_parse.quality import assess
from worker.techstack import find_stack

LOW_CONFIDENCE = 0.55
THIN_SKILLS_THRESHOLD = 3
# Drop skills at or below this LLM confidence.
SKILL_CONF_DROP = 0.35
# Mid-band: keep but dampen years (aligned with role/match years_factor scale).
SKILL_CONF_WEAK = 0.55
SKILL_YEARS_WEAK_FACTOR = 0.5
PROMPT_VERSION = "cv-parse-ai1-v2"
PURPOSE = "cv_parse"

_SYSTEM = """You are a CV extractor. Extract structured facts ONLY from the redacted resume text.

Rules:
- Use only facts present in the text. Do not invent employers, titles, skills, dates, or years.
- Add a skill only when the text contains clear evidence it was used or claimed.
- For every skill: evidence = short quote from the text (≤80 characters); confidence ∈ [0,1].
- "Familiar with", "exposed to", "basic knowledge of" → confidence ≤ 0.4.
- Soft skills (communication, teamwork, leadership, etc.) go ONLY in soft_skills — never in skills.
- seniority: one of intern, junior, middle, senior, lead, principal, staff, or empty.
- total_years and skill years: estimate from work history dates only; do not invent.
- PII placeholders ([NAME], [EMAIL], [PHONE], [URL], [ADDRESS], [CITY]) are redacted — leave contact empty.
- Dates as YYYY-MM or null. end null means current role.

Negative example (do NOT do this):
Title "Backend Engineer" alone must NOT invent Kafka, Kubernetes, or Redis.

Few-shot 1:
Text: "Senior Java Developer at Acme (2019-01–present). Built Spring Boot APIs; Kafka for events."
→ skills: [{name:"Java", years:5, evidence:"Senior Java Developer", confidence:0.95},
  {name:"Spring", years:5, evidence:"Built Spring Boot APIs", confidence:0.9},
  {name:"Kafka", years:null, evidence:"Kafka for events", confidence:0.85}]
  seniority: senior, soft_skills: []

Few-shot 2:
Text: "Junior analyst. Familiar with Python. Strong communication skills."
→ skills: [{name:"Python", years:null, evidence:"Familiar with Python", confidence:0.35}]
  soft_skills: ["communication"]
  Do NOT invent SQL or Excel from the title alone.
"""

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "seniority": {"type": "string"},
        "total_years": {"type": ["number", "null"]},
        "work_history": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "start": {"type": ["string", "null"]},
                    "end": {"type": ["string", "null"]},
                    "summary": {"type": "string"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "company",
                    "location",
                    "start",
                    "end",
                    "summary",
                    "skills",
                ],
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "years": {"type": ["number", "null"]},
                    "level": {"type": "string"},
                    "evidence": {"type": "string"},
                    "confidence": {"type": ["number", "null"]},
                },
                "required": ["name", "years", "level", "evidence", "confidence"],
            },
        },
        "soft_skills": {
            "type": "array",
            "items": {"type": "string"},
        },
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "code": {"type": "string"},
                    "level": {"type": "string"},
                },
                "required": ["code", "level"],
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "degree": {"type": "string"},
                    "field": {"type": "string"},
                    "school": {"type": "string"},
                    "year": {"type": ["integer", "null"]},
                },
                "required": ["degree", "field", "school", "year"],
            },
        },
    },
    "required": [
        "headline",
        "summary",
        "seniority",
        "total_years",
        "work_history",
        "skills",
        "soft_skills",
        "languages",
        "education",
    ],
}


def fallback_enabled(conn: sqlite3.Connection | None = None) -> bool:
    return feature_on("cv_fallback", conn)


def low_confidence_threshold() -> float:
    raw = os.environ.get("CV_AI_LOW_CONFIDENCE", "").strip()
    if not raw:
        return LOW_CONFIDENCE
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return LOW_CONFIDENCE


def dictionary_skill_count(profile: dict) -> int:
    """Count skills that resolve to the packaged dictionary (matching input quality)."""
    raw = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    aliases = _skill_aliases()
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            name_in = item.strip()
        elif isinstance(item, dict):
            name_in = str(item.get("name") or "").strip()
        else:
            continue
        if not name_in:
            continue
        canonical = aliases.get(name_in.lower())
        if not canonical:
            found = find_stack(name_in)
            if len(found) == 1:
                canonical = found[0]
        if canonical and canonical not in seen:
            seen.add(canonical)
    return len(seen)


def _record_quality(meta: dict, q: dict, *, before: float | None = None) -> None:
    meta["quality"] = {
        "score": q["score"],
        "threshold": q["threshold"],
        "issues": list(q["issues"])[:20],
        "weak": list(q["weak"]),
        "version": q["version"],
    }
    if before is not None:
        meta["quality"]["score_before"] = before


def maybe_ai_fallback(
    profile: dict,
    text: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Rules first; ask AI only when the output quality score is low. Never raises.

    The decision looks at the parse *output* (see ``quality.assess``), not at the
    CV template. AI repairs only the weak parts; on any AI failure the rules
    output is kept. ``parse_meta.parse_source`` is rules | ai | mixed.
    """
    meta = profile.setdefault("parse_meta", {})
    if not isinstance(meta, dict):
        meta = {}
        profile["parse_meta"] = meta

    confidence = meta.get("confidence")
    try:
        conf = float(confidence) if confidence is not None else 0.0
    except (TypeError, ValueError):
        conf = 0.0

    quality = assess(profile, text)
    _record_quality(meta, quality)
    meta["parse_source"] = "rules"

    unreadable = [code for code in ("text_too_short", "text_garbled") if code in quality["issues"]]
    if unreadable:
        # Too little / unreadable text (empty, scanned without OCR, garbled glyphs): AI has
        # nothing to work with, so skip the call and keep the rules result.
        meta["ai_fallback"] = "skipped"
        meta["ai_error"] = unreadable[0]
        return profile

    thin = dictionary_skill_count(profile) < THIN_SKILLS_THRESHOLD
    low_conf = conf < low_confidence_threshold()
    if not (quality["needs_ai"] or low_conf or thin):
        return profile
    if not (text or "").strip():
        return profile
    if not fallback_enabled(conn):
        meta["ai_fallback"] = "skipped"
        meta["ai_error"] = "ai_disabled"
        return profile

    reasons = []
    if quality["needs_ai"]:
        reasons.append("quality")
    if low_conf:
        reasons.append("low_confidence")
    if thin:
        reasons.append("thin_skills")
    if thin and not low_conf:
        meta["ai_force_reason"] = "thin_skills"
    meta["ai_reasons"] = reasons

    contact = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    try:
        result = complete_json(
            purpose=PURPOSE,
            prompt_version=PROMPT_VERSION,
            system=_SYSTEM,
            user="Redacted CV text:\n\n" + text[:12000],
            schema=_SCHEMA,
            schema_name="cv_profile",
            known_pii=contact,
            conn=conn,
        )
    except Exception as exc:  # gateway must never break the rules result
        meta["ai_fallback"] = "failed"
        meta["ai_error"] = f"ai_exception:{type(exc).__name__}"
        return profile
    meta["prompt_version"] = PROMPT_VERSION
    if not result.ok or not isinstance(result.data, dict):
        meta["ai_fallback"] = "failed"
        meta["ai_error"] = result.error or "ai_failed"
        return profile

    try:
        weak = set(quality["weak"])
        if quality["score"] < quality["threshold"] or "work_missing" in quality["issues"]:
            weak.add("headline")  # whole parse is weak: headline is unreliable too
        merged = _merge(profile, result.data, text, weak=weak)
    except Exception as exc:
        meta["ai_fallback"] = "failed"
        meta["ai_error"] = f"ai_merge_error:{type(exc).__name__}"
        return profile
    had_structure = bool(profile.get("work_history") or profile.get("education"))
    out_meta = merged.setdefault("parse_meta", {})
    out_meta["method"] = "llm"
    out_meta["parse_source"] = "mixed" if had_structure else "ai"
    out_meta["ai_fallback"] = "applied"
    out_meta["prompt_version"] = PROMPT_VERSION
    out_meta["ai_cached"] = result.cached
    if thin and not low_conf:
        out_meta["ai_force_reason"] = "thin_skills"
    if result.prompt_tokens or result.completion_tokens:
        out_meta["ai_tokens"] = {
            "prompt": result.prompt_tokens,
            "completion": result.completion_tokens,
        }
    after = assess(merged, text)
    _record_quality(out_meta, after, before=quality["score"])
    # Re-score lightly: LLM filled gaps → at least threshold.
    try:
        old = float(out_meta.get("confidence") or 0)
    except (TypeError, ValueError):
        old = 0.0
    out_meta["confidence"] = round(max(old, low_confidence_threshold() + 0.05, 0.6), 2)
    out_meta.pop("ai_error", None)
    return merged


def _merge(rules: dict, llm: dict, text: str, *, weak: set[str] | None = None) -> dict:
    """Merge AI output into rules output, touching only weak/empty parts.

    ``weak=None`` keeps the legacy behaviour (AI may override everything).
    """
    out = dict(rules)
    # Contact always from rules (real PII; LLM saw masks only).
    contact = dict(rules.get("contact") or {})
    if weak is not None and "contact" in weak:
        city = str(contact.get("city") or "")
        if city and "city_is_education" in assess(rules, text)["issues"]:
            contact["city"] = ""
    out["contact"] = contact

    def allowed(part: str, empty: bool) -> bool:
        return weak is None or empty or part in weak

    headline = str(llm.get("headline") or "").strip()[:120]
    if headline and not _has_placeholder(headline) and allowed("headline", not str(rules.get("headline") or "").strip()):
        out["headline"] = headline

    summary = str(llm.get("summary") or "").strip()[:2000]
    if summary and not _has_placeholder(summary):
        if not str(out.get("summary") or "").strip() or len(summary) > len(str(out.get("summary") or "")):
            out["summary"] = summary

    work = _filter_work(llm.get("work_history"), text)
    rules_work = rules.get("work_history") if isinstance(rules.get("work_history"), list) else []
    work_replaced = False
    if work and allowed("work_history", not rules_work):
        if weak is None:
            ok = not rules_work or len(work) >= len(rules_work)
        else:
            ok = not rules_work or len(work) * 2 >= len(rules_work)
        if ok:
            out["work_history"] = work
            work_replaced = True

    seniority = str(llm.get("seniority") or "").strip().lower()
    if seniority in {"intern", "junior", "middle", "senior", "lead", "principal", "staff"}:
        if weak is None or work_replaced or not str(rules.get("seniority") or "").strip():
            out["seniority"] = seniority

    years = llm.get("total_years")
    if isinstance(years, (int, float)) and 0 <= float(years) <= 60:
        if weak is None or work_replaced or not rules.get("total_years"):
            out["total_years"] = float(max(0, int(round(float(years)))))

    skills = filter_skills(llm.get("skills"), text)
    rules_skills = rules.get("skills") if isinstance(rules.get("skills"), list) else []
    if skills:
        out["skills"] = _merge_skills(rules_skills, skills)

    soft = _filter_soft_skills(llm.get("soft_skills"))
    if soft:
        out["soft_skills"] = soft

    languages = _filter_languages(llm.get("languages"))
    if languages and (weak is None or not rules.get("languages")):
        out["languages"] = languages

    education = _filter_education(llm.get("education"))
    if education and allowed("education", not rules.get("education")):
        out["education"] = education

    return out


def filter_skills(raw: object, text: str) -> list[dict]:
    """Keep dictionary skills that also appear in the original CV text.

    Drops LLM confidence ≤ 0.35. Mid-band (≤ 0.55) keeps the skill but
    dampens years so role/match years_factor weighs them less.
    Soft skills must not appear here (LLM schema separates soft_skills).
    """
    if not isinstance(raw, list):
        return []
    aliases = _skill_aliases()
    text_l = (text or "").lower()
    # Also accept skills find_stack already sees in the text.
    in_text_stack = {name.lower() for name in find_stack(text)}
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            name_in, years, level = item, None, ""
            evidence, conf = "", None
        elif isinstance(item, dict):
            name_in = str(item.get("name") or "").strip()
            years = item.get("years")
            level = str(item.get("level") or "").strip()[:40]
            evidence = str(item.get("evidence") or "").strip()[:80]
            conf_raw = item.get("confidence")
            conf = None
            if isinstance(conf_raw, (int, float)):
                conf = max(0.0, min(1.0, float(conf_raw)))
        else:
            continue
        if not name_in:
            continue
        if conf is not None and conf <= SKILL_CONF_DROP:
            continue
        canonical = aliases.get(name_in.lower())
        if not canonical:
            found = find_stack(name_in)
            if len(found) == 1:
                canonical = found[0]
        if not canonical:
            continue
        if canonical.lower() not in in_text_stack and not _skill_in_text(
            canonical, aliases, text_l
        ):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        years_f = None
        if isinstance(years, (int, float)) and 0 <= float(years) <= 60:
            years_f = float(years)
            if conf is not None and conf <= SKILL_CONF_WEAK:
                years_f = years_f * SKILL_YEARS_WEAK_FACTOR
            years_f = float(max(0, int(round(years_f))))
        row: dict[str, Any] = {
            "name": canonical,
            "years": years_f,
            "level": level,
            "source": "cv",
        }
        if evidence:
            row["evidence"] = evidence
        if conf is not None:
            row["confidence"] = conf
        out.append(row)
    return out


def _filter_soft_skills(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item or "").strip()[:60]
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= 12:
            break
    return out


def _skill_in_text(canonical: str, aliases: dict[str, str], text_l: str) -> bool:
    needles = {canonical.lower()}
    for alias, canon in aliases.items():
        if canon == canonical:
            needles.add(alias)
    for needle in needles:
        if len(needle) <= 2:
            if re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text_l):
                return True
        elif needle in text_l:
            return True
    return False


def _merge_skills(rules: list, llm: list[dict]) -> list[dict]:
    by_name: dict[str, dict] = {}
    for item in rules:
        if isinstance(item, dict) and item.get("name"):
            by_name[str(item["name"])] = dict(item)
    for item in llm:
        name = item["name"]
        if name in by_name:
            base = by_name[name]
            if base.get("years") is None and item.get("years") is not None:
                base["years"] = item["years"]
            if not base.get("level") and item.get("level"):
                base["level"] = item["level"]
            if item.get("evidence") and not base.get("evidence"):
                base["evidence"] = item["evidence"]
            if item.get("confidence") is not None and base.get("confidence") is None:
                base["confidence"] = item["confidence"]
        else:
            by_name[name] = item
    return list(by_name.values())


def _filter_work(raw: object, text: str) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:120]
        company = str(item.get("company") or "").strip()[:120]
        if not title and not company:
            continue
        if _has_placeholder(title) or _has_placeholder(company):
            continue
        skill_names = item.get("skills") if isinstance(item.get("skills"), list) else []
        skills = [
            s["name"]
            for s in filter_skills(
                [
                    {
                        "name": str(x),
                        "years": None,
                        "level": "",
                        "evidence": "",
                        "confidence": 0.8,
                    }
                    for x in skill_names
                ],
                text,
            )
        ]
        out.append(
            {
                "title": title,
                "company": company,
                "location": str(item.get("location") or "").strip()[:120],
                "start": _month(item.get("start")),
                "end": _month(item.get("end")),
                "summary": str(item.get("summary") or "").strip()[:400],
                "skills": skills,
            }
        )
        if len(out) >= 20:
            break
    return out


def _filter_languages(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower()[:8]
        if not code or code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "level": str(item.get("level") or "").strip()[:40]})
        if len(out) >= 12:
            break
    return out


def _filter_education(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        school = str(item.get("school") or "").strip()[:200]
        if not school or _has_placeholder(school):
            continue
        year = item.get("year")
        year_i = None
        if isinstance(year, int) and 1950 <= year <= 2100:
            year_i = year
        out.append(
            {
                "degree": str(item.get("degree") or "").strip()[:120],
                "field": str(item.get("field") or "").strip()[:120],
                "school": school,
                "year": year_i,
            }
        )
        if len(out) >= 10:
            break
    return out


def _month(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "present", "current"}:
        return None
    m = re.match(r"^(19|20)\d{2}(?:-(0[1-9]|1[0-2]))?$", text)
    if not m:
        return None
    if len(text) == 4:
        return text + "-01"
    return text


def _has_placeholder(text: str) -> bool:
    return bool(re.search(r"\[(?:NAME|EMAIL|PHONE|URL|ADDRESS|CITY)\]", text or ""))


@lru_cache(maxsize=1)
def _skill_aliases() -> dict[str, str]:
    """lower alias / canonical → canonical name from packaged dictionary."""
    path = Path(__file__).resolve().parents[1] / "skill_dictionary_v1.json"
    mapping: dict[str, str] = {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        # Fall back to techstack names only.
        for name in find_stack(
            " ".join(
                [
                    "Python Java Kotlin Go Rust TypeScript JavaScript PHP Ruby SQL",
                    "AWS Azure GCP Docker Kubernetes PostgreSQL MongoDB Redis Kafka",
                    "React Angular Vue Spring Django FastAPI Node.js",
                ]
            )
        ):
            mapping[name.lower()] = name
        return mapping
    for item in payload.get("skills") or []:
        if not isinstance(item, dict):
            continue
        canonical = str(item.get("canonical_name") or "").strip()
        if not canonical:
            continue
        mapping[canonical.lower()] = canonical
        for syn in item.get("synonyms") or []:
            key = str(syn).strip().lower()
            if key:
                mapping[key] = canonical
    return mapping
