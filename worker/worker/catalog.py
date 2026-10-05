"""Registered sources. Enabled rows are the connectors the worker runs."""

from __future__ import annotations

GO_AT = "2026-10-05T12:00:00+04:00"
GO_BY = "ingress-job plan, worker task 2026-10-05 (foreign remote/relocation tech sources)"

REMOTE_OK_CREDIT = (
    "Listings must show a Remote OK follow link (rel=follow, not nofollow) "
    "to the source URL and must name Remote OK as the source. "
    "The worker calls only https://remoteok.com/api and never ?action=get_jobs."
)


from worker.ats_boards import ATS_MAX_BOARDS, GROUPS as ATS_GROUPS  # noqa: E402


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
# One owner-approved exception: Reed's official keyed API path
# (https://www.reed.co.uk/api/1.0/), see http.ROBOTS_EXCEPTIONS.
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
        'Workable boards (Europe)',
        'https://www.workable.com/',
        'official_api',
        'https://apply.workable.com/api/v1/widget/accounts',
        enabled=True,
        go="go",
        note='Workable açıq karyera widget API (?details=true): Skroutz, Blueground, Persado, Epignosis (Yunanıstan/Avropa). Az elan.',
        credit_note="Employer's public Workable careers widget. The link opens the employer's posting on apply.workable.com.",
    ),
    _row(
        'Recruitee boards (Netherlands)',
        'https://recruitee.com/',
        'official_api',
        'https://bunq.recruitee.com/api/offers/',
        enabled=True,
        go="go",
        note='Recruitee açıq karyera API (/api/offers/): bunq, Channable. Az elan.',
        credit_note="Employer's public Recruitee careers API. The link opens the employer's posting.",
    ),
    _row(
        'Personio boards (Germany)',
        'https://www.personio.com/',
        'rss',
        'https://chrono24.jobs.personio.de/xml',
        enabled=True,
        go="go",
        note='Personio karyera səhifəsinin açıq XML lenti: Chrono24, Taxdoo, 1KOMMA5°, ottonova. robots.txt bağlı olan subdomenlər (taxfix, enpal və s.) çıxarılıb.',
        credit_note="Employer's public Personio career-page XML feed. The link opens the employer's posting.",
    ),
    _row(
        'JobTech Platsbanken (Sweden)',
        'https://jobtechdev.se/',
        'official_api',
        'https://jobsearch.api.jobtechdev.se/search',
        enabled=True,
        go="go",
        note='İsveç dövlət məşğulluq xidmətinin (Arbetsförmedlingen) açıq JobSearch API-si, yalnız Data/IT peşə sahəsi (apaJ_2ja_LuF). İngiliscə elanlar əvvəl gəlir. Açıq data.',
        credit_note='Arbetsförmedlingen JobTech JobSearch API (Platsbanken), open data. The link opens the ad on arbetsformedlingen.se.',
    ),
    _row(
        'Get on Board (Latin America)',
        'https://www.getonbrd.com/',
        'official_api',
        'https://www.getonbrd.com/api/v0/categories/programming/jobs',
        enabled=True,
        go="go",
        note='Get on Board açıq API: Latın Amerikası, proqramlaşdırma, DevOps/QA, data, mobil və kibertəhlükəsizlik kateqoriyaları; remote olanlar işarələnir.',
        credit_note='Get on Board public API. Link back to getonbrd.com and name Get on Board as the source.',
    ),
    _row(
        'Hasjob (India)',
        'https://hasjob.co/',
        'rss',
        'https://hasjob.co/feed',
        enabled=True,
        go="go",
        note='HasGeek Hasjob açıq Atom lenti (Hindistan, son elanlar). Texniki olmayan elanlar başlıqla süzülür.',
        credit_note='Hasjob public Atom feed. The link opens the post on hasjob.co.',
    ),
    _row(
        'WordPress Jobs',
        'https://jobs.wordpress.net/',
        'rss',
        'https://jobs.wordpress.net/feed/',
        enabled=True,
        go="go",
        note='WordPress icmasının rəsmi iş lövhəsinin RSS lenti. Az elan, çoxu remote.',
        credit_note='jobs.wordpress.net public RSS feed. The link opens the post on jobs.wordpress.net.',
    ),
    _row(
        'Remote Python',
        'https://www.remotepython.com/',
        'rss',
        'https://www.remotepython.com/latest/jobs/feed/',
        enabled=True,
        go="go",
        note='Remote Python RSS lenti. Çox az elan (bir neçə ədəd).',
        credit_note='Remote Python public RSS feed. The link opens the post on remotepython.com.',
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
        enabled=True,
        go="go",
        note=(
            "Rəsmi Jooble API (POST jooble.org/api/<açar>), yalnız JOOBLE_API_KEY olduqda işləyir; "
            "açar yoxdursa keçid atlanır. Açarın limiti cəmi 500 sorğudur: ən çox 6 saatda bir, "
            "hər keçiddə 3 IT sorğusu (remote software developer, relocation software engineer, "
            "remote devops engineer), yalnız 1-ci səhifə. Sorğular api_usage cədvəlində ay üzrə "
            "sayılır və ayda 450 sorğuya (JOOBLE_MONTHLY_BUDGET) çatanda Jooble çağırılmır. "
            "Açar loglara yazılmır. Elanın Jooble linki saxlanılır, açılmır; HTML toplanmır."
        ),
        credit_note="Jobs from the Jooble API (jooble.org). The link opens the offer through Jooble.",
        api_key_env="JOOBLE_API_KEY",
    ),
    _row(
        "Reed.co.uk",
        "https://www.reed.co.uk/",
        "official_api",
        "https://www.reed.co.uk/api/1.0/search",
        enabled=True,
        go="go",
        note=(
            "Rəsmi açarlı API (Reed Jobseeker API), yalnız REED_API_KEY olduqda işləyir; açar yoxdursa "
            "keçid atlanır. robots.txt istisnası: www.reed.co.uk/robots.txt bütün botlar üçün "
            "\"Disallow: /api/\" yazır; rəsmi açarlı API, istifadəçi təsdiqi ilə istisna (Aladdin, "
            "2026-10-05) yalnız https://www.reed.co.uk/api/1.0/ yoluna aiddir (http.ROBOTS_EXCEPTIONS); "
            "saytın qalan hissəsi robots.txt-ə tabedir, HTML toplanmır. Dizayn: HTTP Basic (açar "
            "istifadəçi adı), ən çox 6 saatda bir, saniyədə 1 sorğu, 5 IT axtarışı (remote software "
            "developer, software engineer, devops engineer, data engineer, frontend developer), 1-ci "
            "səhifə (50 nəticə), yalnız yeni texniki elan üçün detal sorğusu (keçiddə ən çox 30). "
            "Sorğular api_usage cədvəlində ay üzrə sayılır, REED_MONTHLY_BUDGET (standart 3000) dolanda "
            "Reed çağırılmır. Maaş mənbənin öz valyutası ilə (GBP) salary sütununa yazılır, link "
            "reed.co.uk-dakı orijinal elandır. Reed-in müraciət sayı saxlanmır."
        ),
        credit_note="Jobs from the Reed.co.uk Jobseeker API. The link opens the original ad on reed.co.uk.",
        api_key_env="REED_API_KEY",
    ),
    _row(
        "HeadHunter (hh.ru)",
        "https://hh.ru/",
        "official_api",
        "https://api.hh.ru/vacancies",
        enabled=False,
        go="pending",
        note="Açar olmadan sönülüdür. 2026-10-05 yoxlaması: api.hh.ru/vacancies açarsız sorğuya HTTP 403 qaytarır. Açar (HH_API_KEY) və rəsmi tətbiq qeydiyyatı olmadan çağırılmır; IT peşə rolları (professional_role) ilə məhdudlaşdırılmalıdır.",
        api_key_env="HH_API_KEY",
    ),
]


_ATS_INFO = {
    "greenhouse": (
        "https://www.greenhouse.com/", "official_api", "https://boards-api.greenhouse.io/v1/boards",
        "Greenhouse açıq Job Board API. Siyahı yüngül çağırışdır; mətn, şöbə və ofis yalnız yeni "
        "texniki elan üçün ayrıca çağırılır.",
        "Employer's public Greenhouse job board (Job Board API). The link opens the employer's original posting.",
    ),
    "lever": (
        "https://www.lever.co/", "official_api", "https://api.lever.co/v0/postings",
        "Lever açıq Postings API (tam mətn bir çağırışda). Team/department mənbə kateqoriyasıdır.",
        "Employer's public Lever job board (Postings API). The link opens the employer's original posting on jobs.lever.co.",
    ),
    "teamtailor": (
        "https://www.teamtailor.com/", "rss", "",
        "Teamtailor karyera saytlarının açıq jobs.rss lenti (department, role, remotestatus).",
        "Employer's public Teamtailor career-site RSS feed. The link opens the employer's posting.",
    ),
}


def _ats_rows() -> list[dict]:
    rows = []
    for name, ats, region, boards in ATS_GROUPS:
        home, kind, entry, about, credit = _ATS_INFO[ats]
        if ats == "teamtailor":
            entry = f"https://{boards[0]}.teamtailor.com/jobs.rss"
        rotate = (
            f" Hər keçiddə ən çox {ATS_MAX_BOARDS} lövhə oxunur, qalanları növbəti keçidlərdə növbə ilə."
            if len(boards) > ATS_MAX_BOARDS else ""
        )
        note = (
            f"{region}: işəgötürən lövhələri ({', '.join(boards)}). {about} Ən çox 3 saatda bir "
            f"oxunur, remote elanlar əvvəl, şirkətlər növbə ilə qarışdırılır.{rotate}"
        )
        rows.append(_row(name, home, kind, entry, enabled=True, go="go", note=note, credit_note=credit))
    return rows


# Regional ATS groups sit right before the other employer-board sources.
_at = next(i for i, row in enumerate(SOURCES) if row["name"] == "Workable boards (Europe)")
SOURCES[_at:_at] = _ats_rows()
