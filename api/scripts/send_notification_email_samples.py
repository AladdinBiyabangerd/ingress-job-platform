#!/usr/bin/env python3
"""One-shot: send one sample of each marketing notification email.

Usage (from api/):
  APP_URL=https://web-production-dba98.up.railway.app \\
  EMAIL_HOST=... EMAIL_HOST_USER=... EMAIL_HOST_PASSWORD=... \\
  .venv/bin/python scripts/send_notification_email_samples.py \\
    --to you@example.com

Does not touch email_log / engagement_log. Safe to re-run, but intended once.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sample_match(*, near: bool) -> dict:
    return {
        "title": "Software Engineer (All Levels)",
        "company": "Cadence Solutions",
        "score": 0.56 if near else 0.88,
        "have": ["AWS", "GCP", "MySQL", "PostgreSQL"],
        "missing": ["Kubernetes"] if near else [],
        "remote": True,
        "city": "",
        "explanation": (
            "AWS və PostgreSQL bilikləriniz Cadence Solutions-un bulud əsaslı "
            "proqram təminatı layihələrində istifadə edilən texnologiyalara uyğundur."
        ),
        "job_id": 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="Recipient email")
    parser.add_argument("--lang", default="az", choices=("az", "en", "ru"))
    parser.add_argument(
        "--once-flag",
        default="",
        help="If set, create this file after a successful send and refuse if it exists",
    )
    args = parser.parse_args()
    to = (args.to or "").strip().lower()
    if "@" not in to:
        print("invalid --to", file=sys.stderr)
        return 2

    once = Path(args.once_flag) if args.once_flag else None
    if once and once.is_file():
        print(f"already sent (flag exists): {once}", file=sys.stderr)
        return 0

    if not (os.environ.get("EMAIL_HOST") or "").strip():
        print("EMAIL_HOST is unset — cannot send", file=sys.stderr)
        return 2
    if not (os.environ.get("APP_URL") or os.environ.get("WEB_PUBLIC_DOMAIN") or "").strip():
        print("Set APP_URL (or WEB_PUBLIC_DOMAIN) to the public web origin", file=sys.stderr)
        return 2

    from app.digests import COPY, _build_digest_body, send_marketing_email
    from app.email_templates import (
        render_coach_weekly_html,
        render_digest_html,
        render_match_job_html,
        render_profile_nudge_html,
    )
    from app.engagement import COACH_EMAIL_COPY, NEAR_EMAIL_COPY, NUDGE_EMAIL_COPY

    lang = args.lang
    pack = COPY[lang]
    base = (os.environ.get("APP_URL") or "").rstrip("/")
    # Sample tracked-style paths (not real HMAC — preview only).
    job_url = f"{base}/jobs/1"
    unsub = f"{base}/unsubscribe/preview-sample"
    profile_url = f"{base}/profile/review"
    insights_url = f"{base}/me/insights/roadmap"

    near = _sample_match(near=True)
    high = _sample_match(near=False)
    near_pack = NEAR_EMAIL_COPY[lang]
    nudge_pack = NUDGE_EMAIL_COPY[lang]
    coach_pack = COACH_EMAIL_COPY[lang]

    digest_matches = [
        {**high, "job_id": 1, "score": 0.88, "salary": ""},
        {
            **near,
            "job_id": 2,
            "score": 0.72,
            "title": "Platform Engineer",
            "company": "Northwind Labs",
            "explanation": "Kubernetes və AWS bilikləriniz platform komandasına uyğundur.",
        },
        {
            **high,
            "job_id": 3,
            "score": 0.81,
            "title": "Backend Engineer",
            "company": "PulseRise",
            "remote": True,
            "explanation": "Python və PostgreSQL overlap yüksəkdir.",
        },
        {
            **near,
            "job_id": 4,
            "score": 0.64,
            "title": "Data Engineer",
            "company": "OKKO Soft",
            "city": "Bakı",
            "remote": False,
            "explanation": "SQL güclüdür; Spark əlavə etsəniz skor artar.",
        },
        {
            **high,
            "job_id": 5,
            "score": 0.79,
            "title": "Senior Software Engineer",
            "company": "Adaptiq",
            "explanation": "Full-stack bacarıqlarınız product komandasına uyğundur.",
        },
    ]
    digest_urls = {i: f"{base}/jobs/{i}" for i in range(1, 6)}

    sends: list[tuple[str, str, str, str]] = []

    # 1) match_near
    near_subject = near_pack["subject"].format(title=near["title"])
    near_body = near_pack["body"].format(
        title=near["title"],
        company=near["company"],
        score=56,
        explanation=near["explanation"],
        growth="Öyrən: Kubernetes",
    )
    near_body = near_body + "\n\n" + pack["unsub"] + "\n" + pack["footer"] + "\n"
    near_html = render_match_job_html(
        kind="match_near",
        lang=lang,
        match=near,
        job_url=job_url,
        unsubscribe_url=unsub,
        tip=near["explanation"],
    )
    sends.append(("match_near", near_subject, near_body, near_html))

    # 2) high_match
    high_subject = pack["high_subject"].format(title=high["title"])
    high_body = pack["high_body"].format(
        title=high["title"],
        company=high["company"],
        score=88,
        explanation=high["explanation"],
    )
    high_body = high_body + "\n\n" + pack["unsub"] + "\n" + pack["footer"] + "\n"
    high_html = render_match_job_html(
        kind="high_match",
        lang=lang,
        match=high,
        job_url=job_url,
        unsubscribe_url=unsub,
        tip=high["explanation"],
    )
    sends.append(("high_match", high_subject, high_body, high_html))

    # 3) digest
    digest_subject = pack["digest_subject"]
    digest_body = _build_digest_body(
        user_id="preview",
        lang=lang,
        matches=digest_matches,
        trends=["Python · 22%", "Kubernetes · +8%"],
        gap="Docker",
        unsub=unsub,
        ai_intro="",
    )
    digest_html = render_digest_html(
        lang=lang,
        matches=digest_matches,
        job_urls=digest_urls,
        trends=["Python · 22%", "Kubernetes · +8%"],
        gap="Docker",
        unsubscribe_url=unsub,
        intro="",
    )
    sends.append(("digest", digest_subject, digest_body, digest_html))

    # 4) profile_nudge
    nudge_subject = nudge_pack["subject"]
    nudge_reason = "CV yoxdur · 3-dən az skill"
    nudge_body = nudge_pack["body"].format(reason=nudge_reason)
    nudge_body = nudge_body + "\n\n" + pack["unsub"] + "\n" + pack["footer"] + "\n"
    nudge_html = render_profile_nudge_html(
        lang=lang,
        reason=nudge_reason,
        profile_url=profile_url,
        unsubscribe_url=unsub,
    )
    sends.append(("profile_nudge", nudge_subject, nudge_body, nudge_html))

    # 5) coach_weekly
    role = "Backend Engineer"
    coach_subject = coach_pack["subject"].format(role=role)
    coach_body = coach_pack["body"].format(
        role=role,
        must_learn="Kubernetes, Redis",
        strong="Python, PostgreSQL",
        growth="Öyrən: Kubernetes",
    )
    coach_body = coach_body + "\n\n" + pack["unsub"] + "\n" + pack["footer"] + "\n"
    coach_html = render_coach_weekly_html(
        lang=lang,
        role=role,
        must_learn=["Kubernetes", "Redis"],
        already_strong=["Python", "PostgreSQL"],
        tip="Öyrən: Kubernetes",
        insights_url=insights_url,
        unsubscribe_url=unsub,
    )
    sends.append(("coach_weekly", coach_subject, coach_body, coach_html))

    for kind, subject, body, html_body in sends:
        print(f"sending {kind} → {to} …", flush=True)
        send_marketing_email(
            to=to,
            subject=f"[test] {subject}",
            body=body,
            html_body=html_body,
            unsubscribe_link=unsub,
        )
        print(f"  ok {kind}", flush=True)

    if once:
        once.parent.mkdir(parents=True, exist_ok=True)
        once.write_text(f"sent to {to}\n", encoding="utf-8")
        print(f"wrote once-flag {once}")
    print(f"done: {len(sends)} emails to {to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
