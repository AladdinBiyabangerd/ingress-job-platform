"""Academy-first learning roadmap with AI fallback.

Builds a rich weekly roadmap for Insights + /me/insights/roadmap.
Waterfall per gap: Academy course → career path (alongside courses) → AI milestones.
Soft-fails to locale templates when AI is off or pending.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai_flags import feature_on
from app.ai_gateway import complete_json

log = logging.getLogger("ingress-job.api.learning_roadmap")

PURPOSE = "learning_roadmap"
PROMPT_VERSION = "learning-roadmap-v1"

_LANG_NAME = {"az": "Azerbaijani", "en": "English", "ru": "Russian"}

_CTA = {
    "az": {
        "start_course": "Academy kursuna başla",
        "view_path": "Academy yoluna bax",
        "weekly_tasks": "Həftəlik tapşırıqlar",
        "next_step": "Növbəti addım",
        "view_courses": "Kurslara bax",
        "open_roadmap": "Tam yola bax",
        "practice": "Tətbiq et",
        "recommendations": "Tövsiyələrə bax",
    },
    "en": {
        "start_course": "Start Academy course",
        "view_path": "View Academy path",
        "weekly_tasks": "Weekly tasks",
        "next_step": "Next step",
        "view_courses": "View courses",
        "open_roadmap": "View full path",
        "practice": "Practice now",
        "recommendations": "Open recommendations",
    },
    "ru": {
        "start_course": "Начать курс Academy",
        "view_path": "Смотреть путь Academy",
        "weekly_tasks": "Задачи недели",
        "next_step": "Следующий шаг",
        "view_courses": "Смотреть курсы",
        "open_roadmap": "Смотреть весь путь",
        "practice": "Применить",
        "recommendations": "Открыть рекомендации",
    },
}

_HERO = {
    "az": {
        "title": "Bu həftənin addımı: {skill}",
        "lede": "{skill} biliklərinizi gücləndirmək üçün indi ən uyğun vaxtdır.",
        "motivation": "Bir konkret addım — sonra növbəti skill.",
        "path_title": "{role} öyrənmə yolu",
        "path_lede": "Academy yolu ilə rolunuza doğru konkret addımlar atın.",
        "path_motivation": "Bu həftə path-ə başlayın — sonra praktikaya keçin.",
        "empty_title": "Bu həftənin öyrənmə yolu",
        "empty_lede": "Hələ şəxsi addım yoxdur — tövsiyələrdən rol seçin və ya profili tamamlayın.",
    },
    "en": {
        "title": "This week’s step: {skill}",
        "lede": "Now is a strong time to level up {skill} for your target role.",
        "motivation": "One concrete move — then the next skill.",
        "path_title": "{role} learning path",
        "path_lede": "Take concrete steps toward your role with the Academy path.",
        "path_motivation": "Start the path this week — then practice.",
        "empty_title": "This week’s learning path",
        "empty_lede": "No personal steps yet — pick a role in recommendations or complete your profile.",
    },
    "ru": {
        "title": "Шаг этой недели: {skill}",
        "lede": "Сейчас удачное время усилить {skill} под вашу целевую роль.",
        "motivation": "Один конкретный шаг — затем следующий навык.",
        "path_title": "Путь обучения: {role}",
        "path_lede": "Сделайте конкретные шаги к роли по пути Academy.",
        "path_motivation": "Начните путь на этой неделе — затем практику.",
        "empty_title": "Путь обучения на эту неделю",
        "empty_lede": "Пока нет личных шагов — выберите роль в рекомендациях или заполните профиль.",
    },
}

_PRACTICE_STEPS = {
    "az": (
        "Əsas anlayışları və rəsmi sənədləri öyrən",
        "Kiçik layihədə və ya lab-da tətbiq et",
        "Nəticəni CV və müraciətdə göstər",
    ),
    "en": (
        "Learn the core concepts and official docs",
        "Practice in a small project or lab",
        "Show the result on your CV and applications",
    ),
    "ru": (
        "Изучите основы и официальную документацию",
        "Закрепите на небольшом проекте или в лаборатории",
        "Покажите результат в CV и откликах",
    ),
}

_PATH_STEPS = {
    "az": ("Academy yolunu aç", "Həftəlik praktik tapşırıq", "CV və müraciətdə göstər"),
    "en": ("Open the Academy path", "Weekly practice task", "Show it on CV and applications"),
    "ru": ("Открыть путь Academy", "Недельная практика", "Показать в CV и откликах"),
}

_PATH_WEEK_STEPS = {
    "az": (
        "Academy yoluna bax və ilk moduldan başla",
        "Rol üçün əsas anlayışları möhkəmlət",
        "Nəticəni CV və müraciətdə göstər",
    ),
    "en": (
        "Open the Academy path and start the first module",
        "Strengthen the core concepts for your role",
        "Show the result on your CV and applications",
    ),
    "ru": (
        "Откройте путь Academy и начните первый модуль",
        "Укрепите базовые понятия для роли",
        "Покажите результат в CV и откликах",
    ),
}

_PATH_NEXT_STEPS = {
    "az": (
        {
            "title": "Praktik axına keç",
            "body": "Öyrəndiyinizi kiçik layihə və ya lab-da tətbiq edin.",
        },
        {
            "title": "Rol uyğun elanlara bax",
            "body": "Yaxın elanlarda eyni skill-ləri axtarın və müraciət edin.",
        },
    ),
    "en": (
        {
            "title": "Move into practice",
            "body": "Apply what you learned in a small project or lab.",
        },
        {
            "title": "Browse matching jobs",
            "body": "Find near-miss roles that ask for the same skills and apply.",
        },
    ),
    "ru": (
        {
            "title": "Перейти к практике",
            "body": "Закрепите изученное на небольшом проекте или в лаборатории.",
        },
        {
            "title": "Смотреть подходящие вакансии",
            "body": "Найдите почти подходящие роли с теми же навыками и откликнитесь.",
        },
    ),
}

_WHY_NOW = {
    "az": {
        "course": "Bu skill elanlarda tez-tez çatışmır — Academy kursu ilə bağlayın.",
        "path": "Rolunuz üçün rəsmi Ingress Academy yolu uyğundur.",
        "practice": "Academy kursu hələ yoxdur — praktik addımla boşluğu bağlayın.",
        "apply": "Öyrəndiyinizi yaxın elana tətbiq edin.",
    },
    "en": {
        "course": "This skill often blocks near-miss jobs — close it with an Academy course.",
        "path": "There is an Ingress Academy career path that fits your role.",
        "practice": "No Academy course yet — close the gap with a concrete practice step.",
        "apply": "Apply what you learned to a near-miss job.",
    },
    "ru": {
        "course": "Этот навык часто мешает почти подходящим вакансиям — закройте курсом Academy.",
        "path": "Для вашей роли есть официальный путь Ingress Academy.",
        "practice": "Курса Academy пока нет — закройте пробел практическим шагом.",
        "apply": "Примените изученное к почти подходящей вакансии.",
    },
}

_SYSTEM = (
    "You are a career learning coach speaking directly to the learner. "
    "Build a short, motivating weekly learning roadmap — not a tutorial dump. "
    "Use ONLY skill names from MissingSkills / HaveSkills. Do not invent skills. "
    "Prefer AcademyCourseSlugs / AcademyCareerPath when provided; otherwise give "
    "practice or apply milestones with one concrete next action. "
    "Voice: second person only. No PII. "
    "Spelling: write the requested language with correct orthography. For "
    "Azerbaijani use ə, ı, ö, ü, ğ, ş, ç.\n"
    "Output hero (title, lede, motivation) and 3–5 milestones with kind in "
    "academy_course|academy_path|practice|apply; each needs title, body, why_now, "
    "optional skill, optional academy_slug from the provided slugs."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hero": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "lede": {"type": "string"},
                "motivation": {"type": "string"},
            },
            "required": ["title", "lede", "motivation"],
        },
        "milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "skill": {"type": "string"},
                    "kind": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "why_now": {"type": "string"},
                    "academy_slug": {"type": "string"},
                },
                "required": ["kind", "title", "body", "why_now"],
            },
        },
    },
    "required": ["hero", "milestones"],
}


def roadmap_enabled(conn=None) -> bool:
    return feature_on("learning_roadmap", conn)


def _pick_locale(lang: str | None) -> str:
    text = (lang or "").strip().lower()[:2]
    return text if text in _LANG_NAME else "az"


def _cta_pack(locale: str) -> dict[str, str]:
    return _CTA[_pick_locale(locale)]


def _skill_names(items: list[str] | list[dict[str, Any]] | None, *, limit: int = 12) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("canonical_name") or "").strip()
        else:
            name = str(item or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
        if len(names) >= limit:
            break
    return names


def _parse_course_ids(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if str(x).strip()]


def _academy_courses_for_skills(conn, skill_names: list[str], *, utm_medium: str) -> list[dict[str, str]]:
    from app.digests import academy_course_url

    names = [str(n or "").strip() for n in skill_names if str(n or "").strip()]
    if not names:
        return []
    lower_map = {n.lower(): n for n in names}
    try:
        rows = conn.execute(
            """
            SELECT canonical_name, academy_course_ids
            FROM skill_dictionary
            """
        ).fetchall()
    except Exception:
        return []
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        try:
            cname = str(row["canonical_name"] if "canonical_name" in row.keys() else row[0] or "")
            raw_ids = row["academy_course_ids"] if "academy_course_ids" in row.keys() else row[1]
        except Exception:
            cname = str(row[0] or "") if row else ""
            raw_ids = row[1] if row and len(row) > 1 else "[]"
        key = cname.strip().lower()
        if key not in lower_map or key in seen:
            continue
        courses = _parse_course_ids(raw_ids)
        if not courses:
            continue
        slug = courses[0]
        href = academy_course_url(slug, utm_medium=utm_medium)
        if not href:
            continue
        seen.add(key)
        found.append({"slug": slug, "url": href, "skill": lower_map[key]})
    ordered: list[dict[str, str]] = []
    for name in names:
        for item in found:
            if item["skill"].lower() == name.lower():
                ordered.append(item)
                break
    return ordered


def _taxonomy_path_for_role(conn, role: str) -> tuple[str, str]:
    """Return (canonical_name, path_id) from role_taxonomy when role is known."""
    name = (role or "").strip()
    if not name:
        return "", ""
    try:
        from app.role_suggestions import resolve_taxonomy_role

        resolved = resolve_taxonomy_role(conn, name)
    except Exception:
        resolved = None
    if not isinstance(resolved, dict):
        try:
            row = conn.execute(
                """
                SELECT canonical_name, academy_career_path_id
                FROM role_taxonomy
                WHERE lower(canonical_name) = lower(?)
                LIMIT 1
                """,
                (name,),
            ).fetchone()
        except Exception:
            row = None
        if not row:
            return "", ""
        try:
            return (
                str(row["canonical_name"] if "canonical_name" in row.keys() else row[0] or "").strip(),
                str(
                    row["academy_career_path_id"]
                    if "academy_career_path_id" in row.keys()
                    else row[1] or ""
                ).strip(),
            )
        except Exception:
            return str(row[0] or "").strip(), str(row[1] or "").strip()
    return (
        str(resolved.get("canonical_name") or name).strip(),
        str(resolved.get("academy_career_path_id") or "").strip(),
    )


def _career_path_for_role(
    conn,
    *,
    user_id: str,
    role: str,
    lang: str,
    utm_medium: str,
) -> dict[str, str]:
    from app.academy_paths import academy_career_path_url

    path_id = ""
    role_name = (role or "").strip()
    if role_name:
        canon, path_id = _taxonomy_path_for_role(conn, role_name)
        if canon:
            role_name = canon
    if not path_id and role_name:
        try:
            from app.skill_gap import skill_gap_payload

            gap = skill_gap_payload(conn, user_id=user_id, role=role_name, top=1, lang=lang)
            path_id = str(gap.get("academy_career_path") or "").strip()
        except Exception:
            path_id = ""
    if not path_id:
        try:
            from app.role_suggestions import suggest_roles_payload

            roles = suggest_roles_payload(conn, user_id=user_id, limit=1, lang=lang)
            top = (roles.get("roles") or [None])[0]
            if isinstance(top, dict):
                path_id = str(
                    top.get("academy_career_path") or top.get("academy_career_path_id") or ""
                ).strip()
                if not role_name:
                    role_name = str(top.get("canonical_name") or "").strip()
        except Exception:
            path_id = ""
    if not path_id:
        return {}
    href = academy_career_path_url(path_id, utm_medium=utm_medium)
    if not href:
        return {}
    return {"path_id": path_id, "url": href, "role": role_name}


def _clamp(text: object, *, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _milestone(
    *,
    mid: str,
    kind: str,
    title: str,
    body: str,
    why_now: str,
    cta: dict[str, Any],
    skill: str = "",
    academy_slug: str = "",
    coming_soon: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": mid,
        "kind": kind,
        "title": _clamp(title, limit=120),
        "body": _clamp(body, limit=220),
        "why_now": _clamp(why_now, limit=180),
        "cta": cta,
        "coming_soon": bool(coming_soon),
    }
    if skill:
        out["skill"] = skill
    if academy_slug:
        out["academy_slug"] = academy_slug
    return out


def _template_ai_milestones(
    *,
    locale: str,
    missing: list[str],
    covered: set[str],
) -> list[dict[str, Any]]:
    pack = _cta_pack(locale)
    why = _WHY_NOW[locale]
    steps = _PRACTICE_STEPS[locale]
    out: list[dict[str, Any]] = []
    for index, skill in enumerate(missing):
        if skill.lower() in covered:
            continue
        out.append(
            _milestone(
                mid=f"practice-{index}-{skill.lower().replace(' ', '-')[:40]}",
                kind="practice",
                title=skill,
                body=steps[0],
                why_now=why["practice"],
                cta={
                    "label": pack["practice"],
                    "href": "/me/recommendations",
                    "external": False,
                },
                skill=skill,
                coming_soon=True,
            )
        )
        if len(out) >= 3:
            break
    if not out and missing:
        skill = missing[0]
        out.append(
            _milestone(
                mid="practice-fallback",
                kind="practice",
                title=skill,
                body=steps[1],
                why_now=why["practice"],
                cta={
                    "label": pack["recommendations"],
                    "href": "/me/recommendations",
                    "external": False,
                },
                skill=skill,
                coming_soon=True,
            )
        )
    return out


def _build_academy_milestones(
    *,
    locale: str,
    courses: list[dict[str, str]],
    career: dict[str, str],
) -> list[dict[str, Any]]:
    pack = _cta_pack(locale)
    why = _WHY_NOW[locale]
    hero_pack = _HERO[locale]
    out: list[dict[str, Any]] = []
    for index, course in enumerate(courses[:5]):
        skill = str(course.get("skill") or "").strip()
        slug = str(course.get("slug") or "").strip()
        url = str(course.get("url") or "").strip()
        if not url:
            continue
        out.append(
            _milestone(
                mid=f"course-{index}-{slug or skill.lower().replace(' ', '-')[:40]}",
                kind="academy_course",
                title=skill or slug,
                body=hero_pack["lede"].format(skill=skill or slug),
                why_now=why["course"],
                cta={"label": pack["start_course"], "href": url, "external": True},
                skill=skill,
                academy_slug=slug,
            )
        )
    if career.get("url"):
        role = str(career.get("role") or "").strip()
        path_id = str(career.get("path_id") or "").strip()
        out.append(
            _milestone(
                mid=f"path-{path_id or 'career'}",
                kind="academy_path",
                title=role or path_id,
                body=why["path"],
                why_now=why["path"],
                cta={
                    "label": pack["view_path"],
                    "href": career["url"],
                    "external": True,
                },
                academy_slug=path_id,
            )
        )
    return out


def _validate_ai(
    data: dict[str, Any],
    *,
    missing: list[str],
    have: list[str],
    course_slugs: set[str],
    path_id: str,
) -> dict[str, Any] | None:
    miss_canon = {n.lower(): n for n in missing}
    have_canon = {n.lower(): n for n in have}
    allowed_skills = {**miss_canon, **have_canon}
    raw_hero = data.get("hero") if isinstance(data.get("hero"), dict) else {}
    title = _clamp(raw_hero.get("title"), limit=120)
    lede = _clamp(raw_hero.get("lede"), limit=220)
    motivation = _clamp(raw_hero.get("motivation"), limit=160)
    if len(title) < 8 or len(lede) < 12:
        return None
    kinds = {"academy_course", "academy_path", "practice", "apply"}
    milestones: list[dict[str, Any]] = []
    raw_ms = data.get("milestones") if isinstance(data.get("milestones"), list) else []
    for index, item in enumerate(raw_ms):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        if kind not in kinds:
            continue
        ms_title = _clamp(item.get("title"), limit=120)
        body = _clamp(item.get("body"), limit=220)
        why_now = _clamp(item.get("why_now"), limit=180)
        if len(ms_title) < 3 or len(body) < 8 or len(why_now) < 8:
            continue
        skill_raw = str(item.get("skill") or "").strip()
        skill = ""
        if skill_raw:
            skill = allowed_skills.get(skill_raw.lower(), "")
            if not skill:
                continue
        slug = str(item.get("academy_slug") or "").strip()
        if kind == "academy_course" and slug and slug not in course_slugs:
            slug = ""
        if kind == "academy_path" and path_id:
            slug = path_id
        milestones.append(
            {
                "skill": skill,
                "kind": kind,
                "title": ms_title,
                "body": body,
                "why_now": why_now,
                "academy_slug": slug,
            }
        )
        if len(milestones) >= 5:
            break
    if len(milestones) < 2:
        return None
    return {
        "hero": {"title": title, "lede": lede, "motivation": motivation},
        "milestones": milestones,
    }


def _ai_fill(
    conn,
    *,
    locale: str,
    role: str,
    have: list[str],
    missing: list[str],
    courses: list[dict[str, str]],
    career: dict[str, str],
    near_titles: list[str],
    allow_provider: bool,
) -> tuple[dict[str, Any] | None, str]:
    if not roadmap_enabled(conn):
        return None, "learning_roadmap_disabled"
    if not missing and not courses and not career:
        return None, "no_skills"
    course_slugs = {str(c.get("slug") or "").strip() for c in courses if c.get("slug")}
    path_id = str(career.get("path_id") or "").strip()
    lines = [
        f"Language: {_LANG_NAME[locale]}",
        f"Role: {(role or '').strip() or '(none)'}",
        "HaveSkills: " + (", ".join(have[:10]) if have else "(none)"),
        "MissingSkills: " + (", ".join(missing[:10]) if missing else "(none)"),
        "AcademyCourseSlugs: "
        + (
            ", ".join(f"{c.get('skill')}={c.get('slug')}" for c in courses[:5])
            if courses
            else "(none)"
        ),
        f"AcademyCareerPath: {path_id or '(none)'}",
        "NearMissTitles: " + (", ".join(near_titles[:3]) if near_titles else "(none)"),
        "Write hero + milestones as motivating weekly steps with one concrete action each.",
    ]
    if locale == "az":
        lines.append(
            "Azerbaijani orthography required: ə ı ö ü ğ ş ç. "
            "Correct: tələblərə, təcrübə, mövqe."
        )
    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user="\n".join(lines),
        schema=_SCHEMA,
        schema_name="learning_roadmap",
        known_pii=None,
        conn=conn,
        timeout=30.0,
        allow_provider=allow_provider,
    )
    if not result.ok or not isinstance(result.data, dict):
        code = str(result.error or "ai_failed").strip() or "ai_failed"
        return None, code[:80]
    validated = _validate_ai(
        result.data,
        missing=missing,
        have=have,
        course_slugs=course_slugs,
        path_id=path_id,
    )
    if validated is None:
        return None, "ai_validation_failed"
    return validated, ""


def _attach_ctas(
    ai_milestones: list[dict[str, Any]],
    *,
    locale: str,
    courses: list[dict[str, str]],
    career: dict[str, str],
) -> list[dict[str, Any]]:
    pack = _cta_pack(locale)
    by_skill = {c["skill"].lower(): c for c in courses if c.get("skill")}
    by_slug = {c["slug"]: c for c in courses if c.get("slug")}
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(ai_milestones):
        kind = str(raw.get("kind") or "practice")
        skill = str(raw.get("skill") or "").strip()
        slug = str(raw.get("academy_slug") or "").strip()
        course = by_slug.get(slug) or by_skill.get(skill.lower())
        if kind == "academy_course" and course and course.get("url"):
            cta = {"label": pack["start_course"], "href": course["url"], "external": True}
            slug = course.get("slug") or slug
            coming_soon = False
        elif kind == "academy_path" and career.get("url"):
            cta = {"label": pack["view_path"], "href": career["url"], "external": True}
            slug = career.get("path_id") or slug
            coming_soon = False
        else:
            if kind == "academy_course":
                kind = "practice"
            cta = {
                "label": pack["practice"] if kind != "apply" else pack["recommendations"],
                "href": "/me/recommendations",
                "external": False,
            }
            coming_soon = not bool(course)
        out.append(
            _milestone(
                mid=f"ai-{index}-{kind}",
                kind=kind,
                title=str(raw.get("title") or skill or kind),
                body=str(raw.get("body") or ""),
                why_now=str(raw.get("why_now") or ""),
                cta=cta,
                skill=skill,
                academy_slug=slug,
                coming_soon=coming_soon,
            )
        )
    return out


def _merge_milestones(
    academy: list[dict[str, Any]],
    ai_or_template: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Academy milestones first; fill remaining with AI/template without duplicating skills."""
    covered: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in academy:
        skill = str(item.get("skill") or "").strip().lower()
        if skill:
            covered.add(skill)
        if item.get("kind") == "academy_path":
            covered.add("__path__")
        out.append(item)
    for item in ai_or_template:
        kind = item.get("kind")
        skill = str(item.get("skill") or "").strip().lower()
        if kind == "academy_path" and "__path__" in covered:
            continue
        if kind == "academy_course" and skill and skill in covered:
            continue
        if kind in {"practice", "apply"} and skill and skill in covered:
            continue
        if skill:
            covered.add(skill)
        out.append(item)
        if len(out) >= 8:
            break
    return out


def _source_of(milestones: list[dict[str, Any]]) -> str:
    kinds = {str(m.get("kind") or "") for m in milestones}
    has_academy = bool(kinds & {"academy_course", "academy_path"})
    has_other = bool(kinds & {"practice", "apply"})
    if has_academy and has_other:
        return "hybrid"
    if has_academy:
        return "academy"
    return "ai"


def _sections(
    *,
    locale: str,
    role: str,
    have: list[str],
    missing: list[str],
    milestones: list[dict[str, Any]],
    courses: list[dict[str, str]],
    career: dict[str, str],
    ai_hero: dict[str, str] | None,
) -> dict[str, Any]:
    pack = _cta_pack(locale)
    hero_pack = _HERO[locale]
    has_path_or_course = bool(career or courses)
    role_label = (
        str(career.get("role") or "").strip()
        or str(role or "").strip()
        or "Academy"
    )
    focus = ""
    for item in milestones:
        if item.get("kind") == "academy_course" and item.get("skill"):
            focus = str(item["skill"])
            break
    if not focus:
        for item in milestones:
            if item.get("skill"):
                focus = str(item["skill"])
                break
    if not focus and missing:
        focus = missing[0]

    primary_cta: dict[str, Any]
    if courses and courses[0].get("url"):
        primary_cta = {
            "label": pack["start_course"],
            "href": courses[0]["url"],
            "external": True,
        }
    elif career.get("url"):
        primary_cta = {
            "label": pack["view_path"],
            "href": career["url"],
            "external": True,
        }
    else:
        primary_cta = {
            "label": pack["recommendations"],
            "href": "/me/recommendations",
            "external": False,
        }

    if ai_hero and ai_hero.get("title"):
        hero_title = ai_hero["title"]
        hero_lede = ai_hero.get("lede") or ""
        hero_motivation = ai_hero.get("motivation") or ""
    elif focus:
        hero_title = hero_pack["title"].format(skill=focus)
        hero_lede = hero_pack["lede"].format(skill=focus)
        hero_motivation = hero_pack["motivation"]
    elif has_path_or_course:
        hero_title = hero_pack["path_title"].format(role=role_label)
        hero_lede = hero_pack["path_lede"]
        hero_motivation = hero_pack["path_motivation"]
    else:
        hero_title = hero_pack["empty_title"]
        hero_lede = hero_pack["empty_lede"]
        hero_motivation = ""

    course_ms = [m for m in milestones if m.get("kind") == "academy_course"]
    practice_ms = [m for m in milestones if m.get("kind") in {"practice", "apply"}]
    path_ms = [m for m in milestones if m.get("kind") == "academy_path"]

    week_items: list[dict[str, Any]] = []
    for item in (course_ms + practice_ms)[:4]:
        week_items.append(
            {
                "text": _clamp(item.get("title") or item.get("skill") or "", limit=80),
                "done": False,
                "milestone_id": item.get("id") or "",
            }
        )
    if not week_items and focus:
        for step in _PRACTICE_STEPS[locale][:3]:
            week_items.append({"text": step, "done": False, "milestone_id": ""})
    if not week_items and has_path_or_course:
        for step in _PATH_WEEK_STEPS[locale][:3]:
            week_items.append({"text": step, "done": False, "milestone_id": ""})

    next_pool = practice_ms[1:] if len(practice_ms) > 1 else practice_ms
    if course_ms:
        next_pool = practice_ms + course_ms[1:]
    next_items: list[dict[str, Any]] = []
    for item in next_pool[:4]:
        next_items.append(
            {
                "title": _clamp(item.get("title") or "", limit=80),
                "body": _clamp(item.get("body") or item.get("why_now") or "", limit=160),
                "milestone_id": item.get("id") or "",
            }
        )
    if not next_items:
        for item in milestones[1:4]:
            next_items.append(
                {
                    "title": _clamp(item.get("title") or "", limit=80),
                    "body": _clamp(item.get("body") or item.get("why_now") or "", limit=160),
                    "milestone_id": item.get("id") or "",
                }
            )
    if not next_items and has_path_or_course:
        for item in _PATH_NEXT_STEPS[locale][:2]:
            next_items.append(
                {
                    "title": _clamp(item["title"], limit=80),
                    "body": _clamp(item["body"], limit=160),
                    "milestone_id": "",
                }
            )

    path_steps: list[dict[str, Any]] = []
    if courses:
        for i, course in enumerate(courses[:5]):
            title = str(course.get("skill") or course.get("slug") or "").strip()
            if title:
                path_steps.append({"n": i + 1, "title": title})
    if not path_steps and path_ms:
        path_title = str(path_ms[0].get("title") or role_label).strip()
        if path_title:
            path_steps = [
                {"n": 1, "title": path_title},
                *[{"n": i + 2, "title": t} for i, t in enumerate(_PATH_STEPS[locale][1:])],
            ]
    if not path_steps and has_path_or_course:
        path_steps = [
            {"n": 1, "title": role_label},
            *[{"n": i + 2, "title": t} for i, t in enumerate(_PATH_STEPS[locale][1:])],
        ]

    path_cta = None
    if career.get("url"):
        path_cta = {
            "label": pack["view_path"],
            "href": career["url"],
            "external": True,
        }
    elif courses and courses[0].get("url"):
        path_cta = {
            "label": pack["view_courses"],
            "href": courses[0]["url"],
            "external": True,
        }

    week_cta = primary_cta if primary_cta.get("external") else {
        "label": pack["weekly_tasks"],
        "href": primary_cta.get("href") or "/me/recommendations",
        "external": False,
    }
    if courses and courses[0].get("url"):
        week_cta = {
            "label": pack["start_course"],
            "href": courses[0]["url"],
            "external": True,
        }
    elif career.get("url"):
        week_cta = {
            "label": pack["view_path"],
            "href": career["url"],
            "external": True,
        }

    next_cta = {
        "label": pack["recommendations"],
        "href": "/me/recommendations",
        "external": False,
    }
    if next_pool and next_pool[0].get("cta", {}).get("href"):
        cta0 = next_pool[0]["cta"]
        next_cta = {
            "label": pack["next_step"],
            "href": cta0["href"],
            "external": bool(cta0.get("external")),
        }
    elif career.get("url") and not next_pool:
        next_cta = {
            "label": pack["next_step"],
            "href": career["url"],
            "external": True,
        }

    return {
        "hero": {
            "skill": focus,
            "title": hero_title,
            "lede": hero_lede,
            "motivation": hero_motivation,
            "have": have[:6],
            "missing": missing[:6],
            "cta": primary_cta,
        },
        "this_week": {
            "items": week_items,
            "cta": week_cta,
        },
        "next": {
            "items": next_items,
            "cta": next_cta,
        },
        "academy_path": {
            "path_id": career.get("path_id") or "",
            "role": career.get("role") or role,
            "steps": path_steps if has_path_or_course else [],
            "cta": path_cta,
        }
        if has_path_or_course
        else None,
    }


def legacy_roadmap_steps(
    milestones: list[dict[str, Any]],
    *,
    locale: str,
    missing: list[str],
) -> list[dict[str, Any]]:
    """Notification-friendly {skill, steps, coming_soon} list from rich milestones."""
    locale = _pick_locale(locale)
    by_skill: dict[str, dict[str, Any]] = {}
    for item in milestones:
        skill = str(item.get("skill") or "").strip()
        if not skill:
            continue
        key = skill.lower()
        entry = by_skill.get(key)
        if entry is None:
            entry = {
                "skill": skill,
                "steps": [],
                "coming_soon": bool(item.get("coming_soon")),
            }
            by_skill[key] = entry
        step = str(item.get("title") or item.get("body") or "").strip()
        if step and step not in entry["steps"]:
            entry["steps"].append(step)
        if item.get("coming_soon"):
            entry["coming_soon"] = True
        if item.get("kind") == "academy_course":
            entry["coming_soon"] = False
    out = list(by_skill.values())[:5]
    if out:
        for entry in out:
            if not entry["steps"]:
                entry["steps"] = list(_PRACTICE_STEPS[locale])
            entry["steps"] = entry["steps"][:3]
        return out
    # Pure template when no skill-tagged milestones.
    steps = list(_PRACTICE_STEPS[locale])
    return [
        {"skill": name, "steps": steps, "coming_soon": True}
        for name in missing[:3]
    ]


def build_learning_roadmap(
    conn,
    *,
    user_id: str,
    missing_skills: list[str] | list[dict[str, Any]] | None = None,
    have_skills: list[str] | list[dict[str, Any]] | None = None,
    role: str = "",
    lang: str | None = None,
    near_titles: list[str] | None = None,
    week_key: str = "",
    allow_ai_provider: bool = True,
    utm_medium: str = "roadmap",
) -> dict[str, Any]:
    """Academy-first roadmap; AI fills gaps. Soft-fails to readable templates."""
    locale = _pick_locale(lang)
    missing = _skill_names(missing_skills)
    have = _skill_names(have_skills)
    role_name = (role or "").strip()
    courses = _academy_courses_for_skills(conn, missing, utm_medium=utm_medium)
    career = _career_path_for_role(
        conn,
        user_id=user_id,
        role=role_name,
        lang=locale,
        utm_medium=utm_medium,
    )
    academy_ms = _build_academy_milestones(locale=locale, courses=courses, career=career)
    covered = {
        str(m.get("skill") or "").strip().lower()
        for m in academy_ms
        if m.get("kind") == "academy_course" and m.get("skill")
    }

    ai_status = "skipped"
    ai_hero: dict[str, str] | None = None
    fill_ms: list[dict[str, Any]] = []
    need_ai = bool(missing) and (len(covered) < len(missing) or not academy_ms)
    if need_ai or (not academy_ms and (missing or have or role_name)):
        ai_data, ai_status = _ai_fill(
            conn,
            locale=locale,
            role=role_name,
            have=have,
            missing=missing,
            courses=courses,
            career=career,
            near_titles=[str(t).strip() for t in (near_titles or []) if str(t).strip()][:3],
            allow_provider=allow_ai_provider,
        )
        if ai_data:
            ai_hero = ai_data.get("hero")
            fill_ms = _attach_ctas(
                ai_data.get("milestones") or [],
                locale=locale,
                courses=courses,
                career=career,
            )
            ai_status = "applied"
        elif ai_status == "ai_pending":
            fill_ms = _template_ai_milestones(
                locale=locale, missing=missing, covered=covered
            )
        else:
            fill_ms = _template_ai_milestones(
                locale=locale, missing=missing, covered=covered
            )
            if ai_status in {"", "skipped"}:
                ai_status = "template"
    elif not academy_ms:
        fill_ms = _template_ai_milestones(locale=locale, missing=missing, covered=covered)
        ai_status = "template"

    milestones = _merge_milestones(academy_ms, fill_ms)
    sections = _sections(
        locale=locale,
        role=role_name,
        have=have,
        missing=missing,
        milestones=milestones,
        courses=courses,
        career=career,
        ai_hero=ai_hero,
    )
    source = _source_of(milestones) if milestones else "ai"
    status = "ready"
    if not milestones and not courses and not career:
        # Only block the UI when there is nothing readable to show yet.
        status = "pending" if ai_status == "ai_pending" else "empty"
    # Template/Academy milestones are enough for first paint; do not keep
    # status=pending (that caused 2.5s Insights polling while AI warms).

    pack = _cta_pack(locale)
    cta_primary = sections["hero"]["cta"]["href"] if sections.get("hero") else "/me/insights/roadmap"
    if not str(cta_primary).startswith("http"):
        cta_primary = "/me/insights/roadmap"

    return {
        "role": role_name,
        "week_key": week_key or "",
        "source": source,
        "status": status,
        "ai_status": ai_status,
        "hero": sections["hero"],
        "this_week": sections["this_week"],
        "next": sections["next"],
        "academy_path": sections["academy_path"],
        "milestones": milestones,
        "academy_courses": courses,
        "academy_career_path": career.get("path_id") or "",
        "career_path": career or None,
        "cta_primary": cta_primary,
        "cta_open": {
            "label": pack["open_roadmap"],
            "href": "/me/insights/roadmap",
            "external": False,
        },
        "missing_names": missing,
    }
