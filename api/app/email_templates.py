"""HTML marketing email templates (engagement + digests).

Table-based, inline-CSS layouts for common clients. Plaintext bodies stay
separate; callers pass ``html_body`` into ``send_marketing_email``.
"""

from __future__ import annotations

import html
from typing import Any

_UI = {
    "az": {
        "brand": "Ingress Job",
        "unsub": "Abunəlikdən çıxmaq",
        "footer_tag": "Daha çox karyera imkanları üçün Ingress Job ilə qalın.",
        "benefit_remote": "Uzaqdan işləmək",
        "benefit_remote_sub": "Çevik iş rejimi",
        "benefit_career": "Karyera inkişafı",
        "benefit_career_sub": "Yeni imkanlar",
        "benefit_fit": "Sizə uyğun elanlar",
        "benefit_fit_sub": "AI ilə seçilir",
        "score_label": "Profilinizə uyğun<br>(skor)",
        "skills_match": "{have}/{total} bacarıq uyğundur",
        "skills_none": "Bacarıq uyğunluğu hesablanır",
        "cta_job": "Elanı görüntülə və müraciət et &nbsp; →",
        "cta_digest_job": "Daha çox oxu &nbsp; →",
        "cta_profile": "Profili tamamla &nbsp; →",
        "cta_coach": "Həftəlik plana bax &nbsp; →",
        "remote": "Uzaqdan",
        "match_score": "{score}% uyğun",
        "near_badge_header": "Yaxın elan",
        "near_pill": "◉ &nbsp; Yaxın elan — skill artır",
        "near_lead": "Profilinizə uyğun bir vakansiya tapdıq.<br>Bu elan sizin bacarıqlarınıza və təcrübənizə yaxındır.",
        "high_badge_header": "Yüksək uyğunluq",
        "high_pill": "★ &nbsp; Yüksək uyğunluq",
        "high_lead": "Profilinizə güclü uyğun gələn yeni elan.<br>Bu vakansiya bacarıqlarınıza yaxşı oturur.",
        "digest_badge_header": "Digest",
        "digest_pill": "▣ &nbsp; Bu dövrün uyğun elanları",
        "digest_title": "Sizin üçün seçilmiş elanlar",
        "digest_lead_fallback": "Profilinizə uyğun yeni elanlar:",
        "digest_lead_count": "Bu dəfə sizin üçün <strong>{count}</strong> uyğun elan seçdik.",
        "digest_trends": "Bacarıq trendləri",
        "digest_gap": "Öyrənmə tövsiyəsi",
        "nudge_badge_header": "Profil",
        "nudge_pill": "◎ &nbsp; Profili tamamla",
        "nudge_title": "Uyğun elanlar üçün profilini tamamla",
        "nudge_lead": "CV və bacarıqlarını doldurun ki, sizə uyğun vakansiyaları daha dəqiq tapa bilək.",
        "coach_badge_header": "Kounç",
        "coach_pill": "✦ &nbsp; Bu həftənin planı",
        "coach_lead": "Rolunuza uyğun öyrənmə diqqəti və güclü tərəfləriniz.",
        "coach_learn": "Öyrən",
        "coach_strong": "Güclü tərəflər",
        "role_label": "Rol",
    },
    "en": {
        "brand": "Ingress Job",
        "unsub": "Unsubscribe",
        "footer_tag": "Stay with Ingress Job for more career opportunities.",
        "benefit_remote": "Remote work",
        "benefit_remote_sub": "Flexible schedule",
        "benefit_career": "Career growth",
        "benefit_career_sub": "New opportunities",
        "benefit_fit": "Jobs for you",
        "benefit_fit_sub": "Picked with AI",
        "score_label": "Match to your<br>profile (score)",
        "skills_match": "{have}/{total} skills match",
        "skills_none": "Skill overlap pending",
        "cta_job": "View job and apply &nbsp; →",
        "cta_digest_job": "Read more &nbsp; →",
        "cta_profile": "Complete profile &nbsp; →",
        "cta_coach": "Open weekly plan &nbsp; →",
        "remote": "Remote",
        "match_score": "{score}% match",
        "near_badge_header": "Near miss",
        "near_pill": "◉ &nbsp; Near miss — grow a skill",
        "near_lead": "We found a job close to your profile.<br>A small skill boost could make it a strong match.",
        "high_badge_header": "Strong match",
        "high_pill": "★ &nbsp; Strong match",
        "high_lead": "A new job looks like a strong fit for your profile.<br>Your skills align well with this role.",
        "digest_badge_header": "Digest",
        "digest_pill": "▣ &nbsp; Matches for this period",
        "digest_title": "Jobs picked for you",
        "digest_lead_fallback": "New jobs that fit your profile:",
        "digest_lead_count": "We picked <strong>{count}</strong> matching jobs for you this period.",
        "digest_trends": "Skill trends",
        "digest_gap": "Learning tip",
        "nudge_badge_header": "Profile",
        "nudge_pill": "◎ &nbsp; Complete your profile",
        "nudge_title": "Finish your profile for better matches",
        "nudge_lead": "Add your CV and skills so we can find jobs that fit you.",
        "coach_badge_header": "Coach",
        "coach_pill": "✦ &nbsp; This week’s plan",
        "coach_lead": "Focus skills for your role plus what you already own.",
        "coach_learn": "Learn",
        "coach_strong": "Already strong",
        "role_label": "Role",
    },
    "ru": {
        "brand": "Ingress Job",
        "unsub": "Отписаться",
        "footer_tag": "Оставайтесь с Ingress Job для новых карьерных возможностей.",
        "benefit_remote": "Удалённая работа",
        "benefit_remote_sub": "Гибкий график",
        "benefit_career": "Рост карьеры",
        "benefit_career_sub": "Новые возможности",
        "benefit_fit": "Вакансии для вас",
        "benefit_fit_sub": "Подбор с AI",
        "score_label": "Совпадение с<br>профилем (оценка)",
        "skills_match": "{have}/{total} навыков совпадают",
        "skills_none": "Совпадение навыков считается",
        "cta_job": "Смотреть вакансию и откликнуться &nbsp; →",
        "cta_digest_job": "Читать дальше &nbsp; →",
        "cta_profile": "Заполнить профиль &nbsp; →",
        "cta_coach": "Открыть план недели &nbsp; →",
        "remote": "Удалённо",
        "match_score": "{score}% совпадение",
        "near_badge_header": "Почти совпадение",
        "near_pill": "◉ &nbsp; Почти совпадение — подтяните навык",
        "near_lead": "Нашли вакансию близко к вашему профилю.<br>Небольшой рост навыка может сделать её сильным совпадением.",
        "high_badge_header": "Сильное совпадение",
        "high_pill": "★ &nbsp; Сильное совпадение",
        "high_lead": "Новая вакансия хорошо подходит под ваш профиль.<br>Ваши навыки хорошо совпадают с этой ролью.",
        "digest_badge_header": "Дайджест",
        "digest_pill": "▣ &nbsp; Подходящие вакансии за период",
        "digest_title": "Вакансии для вас",
        "digest_lead_fallback": "Новые вакансии под ваш профиль:",
        "digest_lead_count": "В этот раз мы выбрали для вас <strong>{count}</strong> подходящих вакансий.",
        "digest_trends": "Тренды навыков",
        "digest_gap": "Совет по обучению",
        "nudge_badge_header": "Профиль",
        "nudge_pill": "◎ &nbsp; Заполните профиль",
        "nudge_title": "Заполните профиль для лучших совпадений",
        "nudge_lead": "Добавьте CV и навыки, чтобы мы точнее находили вакансии.",
        "coach_badge_header": "Коуч",
        "coach_pill": "✦ &nbsp; План на неделю",
        "coach_lead": "Навыки для роста по роли и ваши сильные стороны.",
        "coach_learn": "Учить",
        "coach_strong": "Сильные стороны",
        "role_label": "Роль",
    },
}


def _lang(value: str | None) -> str:
    text = (value or "").strip().lower()[:2]
    return text if text in _UI else "az"


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _ui(lang: str | None) -> dict[str, str]:
    return _UI[_lang(lang)]


def _location_label(match: dict[str, Any], *, lang: str) -> str:
    pack = _ui(lang)
    if match.get("remote"):
        return pack["remote"]
    city = str(match.get("city") or "").strip()
    return city or "—"


def _score_pct(match: dict[str, Any]) -> int:
    score = match.get("score")
    if not isinstance(score, (int, float)):
        return 0
    return max(0, min(100, round(float(score) * 100)))


def _skill_chips(skills: list[str], *, limit: int = 6) -> str:
    names = [str(s).strip() for s in skills if str(s).strip()][:limit]
    if not names:
        return ""
    cells: list[str] = []
    for i, name in enumerate(names):
        if i:
            cells.append('<td width="8"></td>')
        cells.append(
            '<td style="padding:11px 14px;background:#d5f4ed;border-radius:24px;'
            f'font-size:14px;font-weight:700;color:#12594f;white-space:nowrap;">{_e(name)}</td>'
        )
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin-top:17px;"><tr>{"".join(cells)}</tr></table>'
    )


def _skills_panel(
    *,
    lang: str,
    have: list[str],
    missing: list[str],
    tip: str,
) -> str:
    pack = _ui(lang)
    have_n = len([s for s in have if str(s).strip()])
    miss_n = len([s for s in missing if str(s).strip()])
    total = have_n + miss_n
    if total > 0:
        headline = pack["skills_match"].format(have=have_n, total=total)
    else:
        headline = pack["skills_none"]
    chips = _skill_chips(have)
    tip_block = ""
    clean_tip = str(tip or "").strip()
    if clean_tip:
        tip_block = (
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            'style="margin-top:19px;"><tr>'
            '<td width="43" valign="top" style="font-size:25px;color:#0b8e82;">☁</td>'
            f'<td style="font-size:14px;line-height:1.75;color:#304c70;">{_e(clean_tip)}</td>'
            "</tr></table>"
        )
    return f"""
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:27px;background:#eafaf7;border-radius:14px;">
                <tr><td style="padding:20px 18px 19px;">
                  <div style="font-size:18px;line-height:1.4;font-weight:800;color:#104b46;"> <span style="display:inline-block;width:27px;height:27px;line-height:27px;text-align:center;border-radius:50%;background:#0aa88f;color:#fff;font-size:16px;">✓</span> &nbsp; {_e(headline)}</div>
                  {chips}
                  {tip_block}
                </td></tr>
              </table>"""


def _cta_button(href: str, label: str) -> str:
    return f"""
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:22px;"><tr>
                <td align="center" bgcolor="#0eaa96" style="border-radius:12px;">
                  <a href="{_e(href)}" target="_blank" style="display:block;padding:18px 15px;font-size:16px;line-height:1.4;font-weight:700;color:#ffffff;text-decoration:none;">{label}</a>
                </td>
              </tr></table>"""


def _benefits(lang: str) -> str:
    pack = _ui(lang)
    return f"""
        <tr><td style="padding:22px 24px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f5f8fc;border-radius:14px;">
            <tr>
              <td width="33.33%" align="center" style="padding:20px 8px;">
                <div style="font-size:22px;color:#0a9d8e;">➤</div><div style="margin-top:8px;font-size:13px;font-weight:700;color:#14213d;">{_e(pack["benefit_remote"])}</div><div style="margin-top:5px;font-size:12px;color:#7283a3;">{_e(pack["benefit_remote_sub"])}</div>
              </td>
              <td width="33.33%" align="center" style="padding:20px 8px;border-left:1px solid #e0e7f0;border-right:1px solid #e0e7f0;">
                <div style="font-size:22px;color:#0a9d8e;">▥</div><div style="margin-top:8px;font-size:13px;font-weight:700;color:#14213d;">{_e(pack["benefit_career"])}</div><div style="margin-top:5px;font-size:12px;color:#7283a3;">{_e(pack["benefit_career_sub"])}</div>
              </td>
              <td width="33.33%" align="center" style="padding:20px 8px;">
                <div style="font-size:22px;color:#0a9d8e;">★</div><div style="margin-top:8px;font-size:13px;font-weight:700;color:#14213d;">{_e(pack["benefit_fit"])}</div><div style="margin-top:5px;font-size:12px;color:#7283a3;">{_e(pack["benefit_fit_sub"])}</div>
              </td>
            </tr>
          </table>
        </td></tr>"""


def _footer(*, lang: str, unsubscribe_url: str) -> str:
    pack = _ui(lang)
    return f"""
        <tr><td style="padding:27px 26px 30px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-top:1px solid #e3e9f1;"><tr>
            <td style="padding-top:22px;font-size:19px;font-weight:800;color:#101a3a;"><span style="color:#0aaf9c;font-size:24px;">✦</span>&nbsp; {_e(pack["brand"])}</td>
            <td align="right" style="padding-top:22px;font-size:12px;line-height:1.7;white-space:nowrap;"><a href="{_e(unsubscribe_url)}" style="color:#7283a3;text-decoration:underline;">{_e(pack["unsub"])}</a></td>
          </tr></table>
          <p style="margin:13px 0 0;font-size:12px;line-height:1.7;color:#8190a9;">{_e(pack["footer_tag"])}</p>
        </td></tr>"""


def _shell(
    *,
    lang: str,
    title: str,
    preheader: str,
    badge_header: str,
    inner: str,
    unsubscribe_url: str,
) -> str:
    pack = _ui(lang)
    return f"""<!doctype html>
<html lang="{_e(_lang(lang))}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="x-apple-disable-message-reformatting">
  <title>{_e(title)}</title>
</head>
<body style="margin:0;padding:0;background:#f2f6fb;font-family:Arial,Helvetica,sans-serif;color:#101a3a;">
  <div style="display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;overflow:hidden;mso-hide:all;">
    {_e(preheader)}
  </div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#f2f6fb;">
    <tr><td align="center" style="padding:24px 10px;">
      <table role="presentation" width="720" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:720px;background:#ffffff;border-radius:18px;overflow:hidden;">
        <tr><td style="padding:28px 34px 24px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
            <td style="font-size:27px;line-height:1.2;font-weight:800;letter-spacing:-.7px;color:#101a3a;">
              <span style="color:#0aaf9c;font-size:31px;vertical-align:-1px;">✦</span>&nbsp;{_e(pack["brand"])}
            </td>
            <td align="right" style="font-size:13px;color:#7283a3;white-space:nowrap;">{_e(badge_header)}</td>
          </tr></table>
        </td></tr>
{inner}
{_benefits(lang)}
{_footer(lang=lang, unsubscribe_url=unsubscribe_url)}
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _hero(*, pill: str, heading_html: str, lead_html: str) -> str:
    return f"""
        <tr><td style="padding:0 12px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#dff8f3;border-radius:18px;">
            <tr><td style="padding:32px 30px 34px;">
              <span style="display:inline-block;padding:10px 15px;border-radius:22px;background:#aaf4e5;color:#087c6e;font-size:13px;font-weight:700;">{pill}</span>
              <h1 style="margin:21px 0 13px;font-size:36px;line-height:1.14;letter-spacing:-1px;color:#101a3a;font-weight:800;">{heading_html}</h1>
              <p style="margin:0;font-size:17px;line-height:1.65;color:#405a7c;">{lead_html}</p>
            </td></tr>
          </table>
        </td></tr>"""


def _job_card(
    *,
    lang: str,
    match: dict[str, Any],
    job_url: str,
    tip: str,
    cta_label: str,
) -> str:
    pack = _ui(lang)
    title = str(match.get("title") or "").strip() or "—"
    company = str(match.get("company") or "").strip() or "—"
    score = _score_pct(match)
    have = [str(x).strip() for x in (match.get("have") or []) if str(x).strip()]
    missing = []
    for entry in match.get("missing") or []:
        if isinstance(entry, dict):
            name = str(entry.get("name") or "").strip()
        else:
            name = str(entry or "").strip()
        if name:
            missing.append(name)
    location = _location_label(match, lang=lang)
    tip_text = tip or str(match.get("explanation") or "").strip()
    return f"""
        <tr><td style="padding:22px 24px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #eaf0f7;border-radius:16px;">
            <tr><td style="padding:25px 24px 24px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
                <td valign="top" style="padding-right:12px;">
                  <div style="font-size:24px;line-height:1.25;font-weight:800;color:#101a3a;">{_e(company)}</div>
                  <p style="margin:15px 0 8px;font-size:15px;line-height:1.5;color:#1c2d50;">▣ &nbsp; {_e(title)}</p>
                  <p style="margin:0;font-size:15px;color:#5b7194;">⌖ &nbsp; {_e(location)}</p>
                </td>
                <td width="150" valign="middle" align="center" style="width:150px;">
                  <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="width:145px;background:#e4f8f4;border-radius:14px;">
                    <tr><td align="center" style="padding:18px 8px;">
                      <div style="font-size:28px;line-height:1.1;font-weight:800;color:#087d6e;">{score}%</div>
                      <div style="margin-top:7px;font-size:12px;line-height:1.4;color:#365d70;">{pack["score_label"]}</div>
                    </td></tr>
                  </table>
                </td>
              </tr></table>
{_skills_panel(lang=lang, have=have, missing=missing, tip=tip_text)}
{_cta_button(job_url, cta_label)}
            </td></tr>
          </table>
        </td></tr>"""


def _title_br(title: str) -> str:
    text = str(title or "").strip() or "—"
    # Soft break for long titles: keep first paren clause on next line when present.
    if "(" in text and text.endswith(")"):
        head, _, rest = text.partition("(")
        head = head.strip()
        if head:
            return f"{_e(head)}<br>({_e(rest)}"
    return _e(text)


def render_match_job_html(
    *,
    kind: str,
    lang: str,
    match: dict[str, Any],
    job_url: str,
    unsubscribe_url: str,
    tip: str = "",
) -> str:
    """HTML for match_near / high_match (match_new email)."""
    pack = _ui(lang)
    title = str(match.get("title") or "").strip() or "—"
    score = _score_pct(match)
    if kind == "match_near":
        badge = pack["near_badge_header"]
        pill = pack["near_pill"]
        lead = pack["near_lead"]
        preheader = f"{title} — {score}% · {badge}"
        page_title = f"Ingress Job — {badge}"
    else:
        badge = pack["high_badge_header"]
        pill = pack["high_pill"]
        lead = pack["high_lead"]
        preheader = f"{title} — {score}% · {badge}"
        page_title = f"Ingress Job — {badge}"
    inner = (
        _hero(pill=pill, heading_html=_title_br(title), lead_html=lead)
        + _job_card(
            lang=lang,
            match=match,
            job_url=job_url,
            tip=tip,
            cta_label=pack["cta_job"],
        )
    )
    return _shell(
        lang=lang,
        title=page_title,
        preheader=preheader,
        badge_header=badge,
        inner=inner,
        unsubscribe_url=unsubscribe_url,
    )


def _digest_snippet(item: dict[str, Any], *, limit: int = 180) -> str:
    text = str(item.get("explanation") or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{cut}…"


def _digest_meta_line(item: dict[str, Any], *, lang: str) -> str:
    pack = _ui(lang)
    bits: list[str] = []
    score = item.get("score")
    if isinstance(score, (int, float)):
        bits.append(pack["match_score"].format(score=round(float(score) * 100)))
    location = _location_label(item, lang=lang)
    if location and location != "—":
        bits.append(location)
    salary = str(item.get("salary") or "").strip()
    if salary:
        bits.append(salary)
    return " · ".join(bits)


def render_digest_html(
    *,
    lang: str,
    matches: list[dict[str, Any]],
    job_urls: dict[int, str],
    trends: list[str],
    gap: str,
    unsubscribe_url: str,
    intro: str = "",
) -> str:
    """Multi-job digest list (Djinni-style feed) inside the shared Ingress shell."""
    pack = _ui(lang)
    job_rows: list[dict[str, Any]] = []
    for item in matches:
        try:
            job_id = int(item.get("job_id") or 0)
        except (TypeError, ValueError):
            continue
        if job_id <= 0:
            continue
        job_rows.append(item)
    count = len(job_rows)
    custom = (intro or "").strip()
    if custom:
        lead = _e(custom)
    elif count > 1:
        lead = pack["digest_lead_count"].format(count=count)
    else:
        lead = _e(pack["digest_lead_fallback"])
    rows: list[str] = []
    for i, item in enumerate(job_rows):
        try:
            job_id = int(item.get("job_id") or 0)
        except (TypeError, ValueError):
            continue
        title = str(item.get("title") or "").strip() or "—"
        company = str(item.get("company") or "").strip() or "—"
        url = job_urls.get(job_id) or ""
        meta = _digest_meta_line(item, lang=lang)
        snippet = _digest_snippet(item)
        top_pad = "0" if i == 0 else "14px"
        snippet_html = (
            f'<p style="margin:12px 0 0;font-size:14px;line-height:1.65;color:#405a7c;">{_e(snippet)}</p>'
            if snippet
            else ""
        )
        meta_html = (
            f'<div style="margin-top:8px;font-size:13px;line-height:1.5;color:#5b7194;">{_e(meta)}</div>'
            if meta
            else ""
        )
        rows.append(
            f"""
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:{top_pad};border:1px solid #eaf0f7;border-radius:14px;">
                <tr><td style="padding:18px 18px 16px;">
                  <div style="font-size:13px;font-weight:700;letter-spacing:.02em;color:#7283a3;">{_e(company)}</div>
                  <div style="margin-top:6px;font-size:18px;line-height:1.3;font-weight:800;color:#101a3a;">{_e(title)}</div>
                  {meta_html}
                  {snippet_html}
                  <div style="margin-top:14px;"><a href="{_e(url)}" target="_blank" style="font-size:14px;font-weight:700;color:#0eaa96;text-decoration:none;">{pack["cta_digest_job"]}</a></div>
                </td></tr>
              </table>"""
        )
    extra = ""
    if trends:
        items = "".join(f'<div style="margin-top:6px;font-size:14px;color:#405a7c;">• {_e(t)}</div>' for t in trends)
        extra += f"""
              <div style="margin-top:22px;font-size:16px;font-weight:800;color:#104b46;">{_e(pack["digest_trends"])}</div>
              {items}"""
    if gap:
        extra += f"""
              <div style="margin-top:18px;font-size:16px;font-weight:800;color:#104b46;">{_e(pack["digest_gap"])}</div>
              <div style="margin-top:6px;font-size:14px;line-height:1.6;color:#405a7c;">{_e(gap)}</div>"""
    card = f"""
        <tr><td style="padding:22px 24px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #eaf0f7;border-radius:16px;">
            <tr><td style="padding:22px 20px 20px;">
              {"".join(rows) or '<div style="font-size:14px;color:#5b7194;">—</div>'}
              {extra}
            </td></tr>
          </table>
        </td></tr>"""
    preheader = custom or (
        pack["digest_lead_count"].format(count=count).replace("<strong>", "").replace("</strong>", "")
        if count > 1
        else pack["digest_lead_fallback"]
    )
    inner = (
        _hero(
            pill=pack["digest_pill"],
            heading_html=_e(pack["digest_title"]),
            lead_html=lead,
        )
        + card
    )
    return _shell(
        lang=lang,
        title=f"Ingress Job — {pack['digest_badge_header']}",
        preheader=preheader,
        badge_header=pack["digest_badge_header"],
        inner=inner,
        unsubscribe_url=unsubscribe_url,
    )


def render_profile_nudge_html(
    *,
    lang: str,
    reason: str,
    profile_url: str,
    unsubscribe_url: str,
) -> str:
    pack = _ui(lang)
    reason_html = _e(reason) if reason else ""
    card = f"""
        <tr><td style="padding:22px 24px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #eaf0f7;border-radius:16px;">
            <tr><td style="padding:25px 24px 24px;">
              <div style="font-size:16px;line-height:1.65;color:#405a7c;">{reason_html}</div>
{_cta_button(profile_url, pack["cta_profile"])}
            </td></tr>
          </table>
        </td></tr>"""
    inner = (
        _hero(
            pill=pack["nudge_pill"],
            heading_html=_e(pack["nudge_title"]),
            lead_html=pack["nudge_lead"],
        )
        + card
    )
    return _shell(
        lang=lang,
        title=f"Ingress Job — {pack['nudge_badge_header']}",
        preheader=pack["nudge_title"],
        badge_header=pack["nudge_badge_header"],
        inner=inner,
        unsubscribe_url=unsubscribe_url,
    )


def render_coach_weekly_html(
    *,
    lang: str,
    role: str,
    must_learn: list[str],
    already_strong: list[str],
    tip: str,
    insights_url: str,
    unsubscribe_url: str,
) -> str:
    pack = _ui(lang)
    role_text = str(role or "").strip() or "—"
    learn_chips = _skill_chips(must_learn, limit=8)
    strong_chips = _skill_chips(already_strong, limit=8)
    tip_block = ""
    if tip:
        tip_block = f'<p style="margin:16px 0 0;font-size:14px;line-height:1.7;color:#304c70;">{_e(tip)}</p>'
    card = f"""
        <tr><td style="padding:22px 24px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #eaf0f7;border-radius:16px;">
            <tr><td style="padding:25px 24px 24px;">
              <div style="font-size:13px;font-weight:700;color:#7283a3;text-transform:uppercase;letter-spacing:.04em;">{_e(pack["role_label"])}</div>
              <div style="margin-top:8px;font-size:24px;font-weight:800;color:#101a3a;">{_e(role_text)}</div>
              <div style="margin-top:22px;font-size:16px;font-weight:800;color:#104b46;">{_e(pack["coach_learn"])}</div>
              {learn_chips or '<div style="margin-top:10px;font-size:14px;color:#5b7194;">—</div>'}
              <div style="margin-top:20px;font-size:16px;font-weight:800;color:#104b46;">{_e(pack["coach_strong"])}</div>
              {strong_chips or '<div style="margin-top:10px;font-size:14px;color:#5b7194;">—</div>'}
              {tip_block}
{_cta_button(insights_url, pack["cta_coach"])}
            </td></tr>
          </table>
        </td></tr>"""
    inner = (
        _hero(
            pill=pack["coach_pill"],
            heading_html=_e(role_text),
            lead_html=pack["coach_lead"],
        )
        + card
    )
    return _shell(
        lang=lang,
        title=f"Ingress Job — {pack['coach_badge_header']}",
        preheader=f"{pack['coach_badge_header']}: {role_text}",
        badge_header=pack["coach_badge_header"],
        inner=inner,
        unsubscribe_url=unsubscribe_url,
    )
