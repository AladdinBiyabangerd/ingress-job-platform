"""Registered sources. Enabled rows are the connectors the worker runs."""

from __future__ import annotations

GO_AT = "2026-10-04T12:00:00+04:00"
GO_BY = "ingress-job plan, worker task 2026-10-04"

REMOTE_OK_CREDIT = (
    "Listings must show a Remote OK follow link (rel=follow, not nofollow) "
    "to the source URL and must name Remote OK as the source. "
    "The worker calls only https://remoteok.com/api and never ?action=get_jobs."
)


def _row(
    name: str,
    homepage: str,
    connector: str,
    entry_url: str,
    *,
    enabled: bool,
    go: str,
    note: str,
    credit_note: str = "",
    api_key_env: str = "",
) -> dict:
    return {
        "name": name,
        "homepage": homepage,
        "connector": connector,
        "entry_url": entry_url,
        "enabled": 1 if enabled else 0,
        "min_delay_seconds": 1,
        "go_decision": go,
        "go_decided_by": GO_BY if go == "go" else "",
        "go_decided_at": GO_AT if go == "go" else "",
        "credit_note": credit_note,
        "api_key_env": api_key_env,
        "note": note,
    }


# LinkedIn, Indeed, Tap.az, gloria.az and job.az are intentionally absent.
SOURCES: list[dict] = [
    _row(
        "Busy.az",
        "https://busy.az/",
        "sitemap",
        "https://busy.az/sitemap_all.xml",
        enabled=True,
        go="go",
        note="Sitemap, sonra açıq vakansiya səhifəsi. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "Boss.az",
        "https://boss.az/",
        "sitemap",
        "https://boss.az/sitemap.xml",
        enabled=True,
        go="go",
        note="Sitemap. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "HelloJob",
        "https://www.hellojob.az/",
        "sitemap",
        "https://www.hellojob.az/sitemap.xml",
        enabled=True,
        go="go",
        note="Sitemap. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "We Work Remotely",
        "https://weworkremotely.com/",
        "rss",
        "https://weworkremotely.com/remote-jobs.rss",
        enabled=True,
        go="go",
        note="Açıq RSS. Partnyor API çağırılmır. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "Remote OK",
        "https://remoteok.com/",
        "json_api",
        "https://remoteok.com/api",
        enabled=True,
        go="go",
        note="Yalnız JSON API. ?action=get_jobs çağırılmır.",
        credit_note=REMOTE_OK_CREDIT,
    ),
    _row(
        "Glorri",
        "https://jobs.glorri.az/",
        "open_list",
        "https://jobs.glorri.az/",
        enabled=True,
        go="go",
        note="Açıq siyahı, sonra vakansiya səhifəsi. /_next/ yox. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "JobSearch.az",
        "https://jobsearch.az/",
        "open_list",
        "https://jobsearch.az/vacancies",
        enabled=True,
        go="go",
        note="Açıq /vacancies siyahısı. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "HRX",
        "https://hrx.az/",
        "open_list",
        "https://hrx.az/is-elanlari",
        enabled=True,
        go="go",
        note="Açıq siyahı. /api/ çağırılmır. Sitemap 403 olduğu üçün oxunmur. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "Work.az",
        "https://www.work.az/",
        "open_list",
        "https://www.work.az/vakansiyalar",
        enabled=True,
        go="go",
        note="Açıq siyahı. Giriş və kabinet yox. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "eJob.az",
        "https://ejob.az/",
        "sitemap",
        "https://ejob.az/sitemap/sitemap.xml",
        enabled=True,
        go="go",
        note="Yalnız vakansiya sitemap-i. CV sitemap-i yox. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "hh1.az",
        "https://hh1.az/",
        "open_list",
        "https://hh1.az/vacancies",
        enabled=True,
        go="go",
        note="Açıq /vacancy/ səhifələri. Sorğu sətri, RSS və CV yox. hh.ru API deyil. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "Djinni",
        "https://djinni.co/",
        "rss",
        "https://djinni.co/jobs/rss/",
        enabled=True,
        go="go",
        note="Açıq RSS. /jobs2, /q və bağlanmış elanlar yox. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "Wellfound",
        "https://wellfound.com/",
        "open_list",
        "https://wellfound.com/jobs",
        enabled=True,
        go="go",
        note="Açıq /jobs siyahısı. /search toplanmır. Hər keçiddə ən çox 30 yeni elan.",
    ),
    _row(
        "Dice",
        "https://www.dice.com/",
        "open_list",
        "https://www.dice.com/jobs",
        enabled=False,
        go="pending",
        note="Sönülüdür. robots.txt Disallow: /job ilk uyğunluqla /jobs və /job-detail yolunu bağlayır. Sorğu sətirli axtarış və RSS də bağlıdır.",
    ),
    _row(
        "hh.ru",
        "https://hh.ru/",
        "official_api",
        "https://api.hh.ru/vacancies",
        enabled=False,
        go="pending",
        note="Açar olmadan sönülüdür. HTML toplanmır.",
        api_key_env="HH_API_KEY",
    ),
    _row(
        "Jooble",
        "https://jooble.org/",
        "official_api",
        "https://jooble.org/api/",
        enabled=False,
        go="pending",
        note="Açar olmadan sönülüdür. HTML toplanmır.",
        api_key_env="JOOBLE_API_KEY",
    ),
    _row(
        "Reed.co.uk",
        "https://www.reed.co.uk/",
        "official_api",
        "https://www.reed.co.uk/api/1.0/search",
        enabled=False,
        go="pending",
        note="Açar olmadan sönülüdür. /api/ açarsız çağırılmır. HTML toplanmır.",
        api_key_env="REED_API_KEY",
    ),
]
