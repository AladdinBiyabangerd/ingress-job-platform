"""Registered sources. Enabled rows are the connectors the worker runs."""

from __future__ import annotations

GO_AT = "2026-10-05T12:00:00+04:00"
GO_BY = "ingress-job plan, worker task 2026-10-05 (foreign remote/relocation tech sources)"

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


# Foreign tech job sources with remote or relocation (visa) focus only.
# Domestic Azerbaijani boards (Busy.az, Boss.az, HelloJob, Glorri, JobSearch.az,
# HRX, Work.az, eJob.az, hh1.az) and hh.ru were removed on 2026-10-05. Their
# rows stay in crawl_sources switched off (go_decision 'retired') and their
# stored ads are kept but hidden once (db.hide_retired_local); nothing collects
# them any more.
# LinkedIn, Indeed, Tap.az, gloria.az and job.az are intentionally absent.
# Every enabled row: robots.txt allows the exact URLs read, the source terms do
# not forbid it, there is no login wall or bot challenge, and at most 30 new
# ads are saved per source per pass.
SOURCES: list[dict] = [
    _row(
        "We Work Remotely",
        "https://weworkremotely.com/",
        "rss",
        "https://weworkremotely.com/remote-jobs.rss",
        enabled=True,
        go="go",
        note="Açıq RSS. Partnyor API çağırılmır. Yalnız IT elanları. Hər keçiddə ən çox 30 yeni elan.",
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
        "Arbeitnow",
        "https://www.arbeitnow.com/",
        "official_api",
        "https://www.arbeitnow.com/api/job-board-api",
        enabled=True,
        go="go",
        note="Pulsuz açıq API. visa_sponsorship=true və remote elanlar. Yalnız IT.",
        credit_note="Arbeitnow free Job Board API. Link back to arbeitnow.com and name Arbeitnow as the source.",
    ),
    _row(
        "Himalayas",
        "https://himalayas.app/",
        "official_api",
        "https://himalayas.app/jobs/api/search",
        enabled=True,
        go="go",
        note="Rəsmi açıq API (açarsız). Gündə bir dəfə. HTML toplanmır (saytın şərtləri scraping-i qadağan edir).",
        credit_note="Himalayas Remote Jobs API. Show a visible link back to himalayas.app and say the data is sourced from Himalayas.",
    ),
    _row(
        "Jobicy",
        "https://jobicy.com/",
        "official_api",
        "https://jobicy.com/api/v2/remote-jobs",
        enabled=True,
        go="go",
        note="Rəsmi açıq Jobs API. Ən tez 3 saatdan bir. Remote elanlar.",
        credit_note="Jobicy public Jobs API. Credit Jobicy with a direct link to the source; the apply button must lead to the Jobicy listing URL from the feed.",
    ),
    _row(
        "Working Nomads",
        "https://www.workingnomads.com/",
        "official_api",
        "https://www.workingnomads.com/api/exposed_jobs/",
        enabled=True,
        go="go",
        note="Saytın özünün göstərdiyi açıq JSON API. Remote elanlar.",
        credit_note="Working Nomads public jobs API. Name Working Nomads as the source.",
    ),
    _row(
        "4 Day Week",
        "https://4dayweek.io/",
        "official_api",
        "https://4dayweek.io/api/v2/jobs",
        enabled=True,
        go="go",
        note="Rəsmi açıq v2 API (engineering, remote). HTML scraping şərtlərlə qadağandır, toplanmır.",
        credit_note="4dayweek.io public API. Link back to https://4dayweek.io.",
    ),
    _row(
        "HN Who is hiring",
        "https://news.ycombinator.com/",
        "official_api",
        "https://hn.algolia.com/api/v1/search_by_date",
        enabled=True,
        go="go",
        note="Algolia HN Search API: son 'Who is hiring?' mövzusu. Yalnız REMOTE və ya VISA qeyd olunanlar. news.ycombinator.com oxunmur.",
        credit_note="Hacker News 'Who is hiring?' thread via the Algolia HN Search API.",
    ),
    _row(
        "Python.org Jobs",
        "https://www.python.org/jobs/",
        "rss",
        "https://www.python.org/jobs/feed/rss/",
        enabled=True,
        go="go",
        note="Açıq RSS. Yalnız remote və ya viza/relokasiya elanları.",
    ),
    _row(
        "Crypto Jobs List",
        "https://cryptojobslist.com/",
        "rss",
        "https://api.cryptojobslist.com/jobs.rss",
        enabled=True,
        go="go",
        note="Açıq RSS. Elan səhifəsi oxunmur. Yalnız IT və remote/relokasiya.",
    ),
    _row(
        "Real Work From Anywhere",
        "https://www.realworkfromanywhere.com/",
        "rss",
        "https://www.realworkfromanywhere.com/rss.xml",
        enabled=True,
        go="go",
        note="Açıq RSS, dünya üzrə remote. /go/ (robots bağlı) oxunmur.",
    ),
    _row(
        "Berlin Startup Jobs",
        "https://berlinstartupjobs.com/",
        "rss",
        "https://berlinstartupjobs.com/feed/",
        enabled=True,
        go="go",
        note="Açıq RSS, mətn qısa olanda açıq elan səhifəsi (JobPosting). İngilis dilli Berlin startap elanları.",
    ),
    _row(
        "Golang Projects",
        "https://www.golangprojects.com/",
        "rss",
        "https://www.golangprojects.com/rss.xml",
        enabled=True,
        go="go",
        note="Açıq RSS, sonra açıq elan səhifəsi (JobPosting). Go elanları.",
    ),
    _row(
        "Elixir Jobs",
        "https://elixirjobs.net/",
        "rss",
        "https://elixirjobs.net/rss",
        enabled=True,
        go="go",
        note="Açıq RSS, sonra açıq elan səhifəsi (JobPosting). Elixir elanları.",
    ),
    _row(
        "Jobspresso",
        "https://jobspresso.co/",
        "rss",
        "https://jobspresso.co/feed/job_feed/",
        enabled=True,
        go="go",
        note="Açıq iş RSS-i (yol ilə). robots.txt '/*?' bağladığı üçün sorğu sətirli feed oxunmur. Crawl-delay 3.",
    ),
    _row(
        "Relocate.me",
        "https://relocate.me/",
        "open_list",
        "https://relocate.me/international-jobs",
        enabled=True,
        go="go",
        note="Açıq siyahı, sonra elan səhifəsi. Hər elan relokasiya paketi ilə.",
    ),
    _row(
        "Japan Dev",
        "https://japan-dev.com/",
        "open_list",
        "https://japan-dev.com/jobs",
        enabled=True,
        go="go",
        note="Açıq siyahı, sonra elan səhifəsi (JobPosting). Yaponiyada ingilisdilli IT, çoxu viza ilə.",
    ),
    _row(
        "Remote First Jobs",
        "https://remotefirstjobs.com/",
        "open_list",
        "https://remotefirstjobs.com/jobs/software-development",
        enabled=True,
        go="go",
        note="Açıq kateqoriya siyahısı, sonra elan səhifəsi (JobPosting). /api/ çağırılmır.",
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
