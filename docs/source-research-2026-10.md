# Mənbə araşdırması — 2026-10-11 (commit olunmayıb)

Məqsəd: elan mənbələrinin sayını və **qəbul olunan** (Azərbaycandan remote və ya relocation/viza) elanların gündəlik sayını artırmaq.
Heç bir kod və real DB dəyişdirilməyib. Bütün ölçmələr müvəqqəti SQLite fayllarında, mövcud `finish_item` qəbul məntiqi ilə (AI söndürülü, API açarları götürülüb), kənar çağırışlar yalnız açıq (public) endpoint-lərə edilib.

## 0. Əsas nəticə (qısa)

1. Problem "sayt azdır" deyil, **şirkət lövhələrinin (slug) azlığıdır**. Repoda cəmi ~193 Greenhouse, 42 Lever, 9 Workable, 5 Recruitee, 4 Personio, 19 Teamtailor slug var. İctimai siyahılarda isə: Greenhouse ~4 800+, Lever ~2 100, Ashby ~3 400+, Workable ~4 750, Personio ~2 460, Teamtailor ~1 460, Recruitee ~1 160, Breezy ~1 385, Rippling ~1 920, BambooHR ~5 600, Pinpoint ~400 (mənbələr bölmə 3-də).
2. Təsadüfi slug əlavə etmək **işləmir**: 390 təsadüfi lövhədə (Greenhouse 130, Lever 90, Workable 60, Recruitee 40, Personio 40, Teamtailor 30) qəbul olunan elan yalnız Greenhouse (26 elan, 8 lövhə) və Lever (2 elan, 2 lövhə) idi; Workable/Recruitee/Personio/Teamtailor-da **0**.
3. **İki mərhələli süzgəc işləyir**: 1-ci mərhələ yüngül siyahı çağırışı (1 sorğu/lövhə) ilə texniki başlıqlı elanların yerində "Remote/Anywhere/Global/EMEA/relocation/visa" siqnalı olan lövhələri tapır; 2-ci mərhələ qəbul məntiqini işlədir. Siqnallı lövhələrdə (ən güclü 110 Greenhouse + 70 Lever) 28/110 Greenhouse və 12/70 Lever lövhəsi məhsuldar oldu (100 və 70 qəbul olunan elan). Bu, təsadüfi seçimdən ~3 dəfə yüksəkdir.
4. Rəsmi yerli iş saytları (Sinqapur MyCareersFuture) texniki elan çox verir, amma **0/998** qəbul olundu → faydasızdır.
5. Qeyd: AI söndürülü olduğu üçün "Remote" yazılan, region məhdudiyyəti mətndə açıq olmayan elanlar qəbul sayılıb; real pipeline-da AI və region qaydaları bəzilərini rədd edəcək (ABŞ-yönümlü şirkətlərdə). Ona görə rəqəmlər **yuxarı həd**, "təmiz" siyahı isə aşağıda ayrıca işarələnib.

## 1. Mövcud mənbələr (təkrar təklif olunmur)

We Work Remotely, Remote OK, Djinni, Wellfound, Arbeitnow, Himalayas, Jobicy, Working Nomads, Jobgether, RemoteYeah, 4 Day Week, HN Who is hiring, Python.org Jobs, Crypto Jobs List, Real Work From Anywhere, Berlin Startup Jobs, Golang Projects, Elixir Jobs, Jobspresso, Relocate.me, Japan Dev, Remote First Jobs (RSS), DevITjobs UK, The Muse, JobTech Platsbanken, Get on Board, Hasjob, WordPress Jobs, Remote Python, Dice, Jooble, Reed, HeadHunter + ATS qrupları: Greenhouse (15 region qrupu, ~193 slug), Lever (4 qrup, 42), Teamtailor (2 qrup, 19), Workable (9), Recruitee (5), Personio (4).
Qeyd: **JobsCollider RSS = Remote First Jobs-un eyni lenti** (301 ilə `remotefirstjobs.com`-a yönləndirir) → təkrardır.

## 2. Ölçmə metodikası

- `/tmp` altında müvəqqəti skriptlər (repoya yazılmayıb): mövcud `GreenhouseConnector/LeverConnector/WorkableConnector/RecruiteeConnector/PersonioConnector/TeamtailorConnector` siniflərindən hər slug üçün ayrıca nüsxə, müvəqqəti `Store`, `finish_item` (techstack + region qaydaları + `foreign_office_without_offer` + `az_market_relevant`), AI yoxdur (qeyri-aydın elanlar rədd sayılır → aşağı hədd).
- Yeni platformalar (Workable aggregator, RSS lentlər, MyCareersFuture) üçün eyni `finish_item` ilə sadə adapter.
- robots.txt hər host üçün stdlib parser ilə (bot adı və `*`) yoxlanıb; mövcud `PoliteClient` isə dry-run-larda robots-u özü tətbiq edib.
- `cands` hər lövhədə texniki başlıqlı yeni elanlar, `acc` qəbul olunanlar. Gündəlik rəqəm = inventar / ~30 gün (təxmini ömür); **ölçülməyib, ehtimaldır**.

## 3. ATS slug siyahı mənbələri (açıq, yoxlanıb, hamısı GitHub/datahub)

| Mənbə | Məzmun | URL |
|---|---|---|
| kalil0321/ats-scrapers `ats-companies/*.csv` | name,slug,url: greenhouse 6 031, lever 2 402, workable 4 752, recruitee 1 164, personio 2 463, teamtailor 1 464, breezy 1 384, ashby 3 448, rippling 1 923, gem 496, pinpoint 406, join_com 23 547, bamboohr 5 632, jazzhr 2 689, smartrecruiters 2 747 | github.com/kalil0321/ats-scrapers/tree/main/ats-companies |
| LastRound AI ATS directory (CSV, 2026-08) | greenhouse 4 966, lever 2 113, ashby 2 856 (şirkət adı + slug + son yoxlama tarixi) | datahub.io/lastroundai-hiring-data/lastroundai-hiring-data/ats-directory |
| Feashliaa/job-board-aggregator `data/*_companies.json` | Common Crawl-dan ~95 000 identifikator (greenhouse, lever, ashby, bamboohr, icims, paylocity, workday) | github.com/Feashliaa/job-board-aggregator/tree/main/data |
| ever-jobs COMPANY_SLUG_DIRECTORY.md, ConorsCode/open-jobs-data, Thelastpoet/africa-ats-directory | kiçik, kurasiya olunmuş siyahılar (Afrika şirkətləri xüsusi maraqlıdır) | GitHub |
| Viza/relocation siyahıları: shubheksha/companies-sponsoring-visas, AndrewStetsenko/tech-jobs-with-relocation, geshan/au-companies-providing-work-visa-sponsorship, Lamiiine/Awesome-daily-list-of-visa-sponsored-jobs | viza verən şirkətlər (karyera URL-ləri → ATS slug çıxarmaq olar), Lamiiine siyahısı gündəlik yenilənən markdown cədvəldir | GitHub |
| Rəsmi sponsor reyestrləri (UK Licensed Sponsors, NL IND recognised sponsors, ABŞ DOL LCA/H-1B) | sponsor şirkət adları → ATS slug uyğunlaşdırmaq üçün lead siyahısı (elan deyil) | gov.uk, ind.nl, dol.gov |

Mövcud slug-lar çıxarılandan sonra namizəd hovuz: Greenhouse ~4 780, Lever ~2 070, Workable ~4 745, Recruitee ~1 160, Personio ~2 460, Teamtailor ~1 457.

## 4. ATS slug ölçmələri (əsas nəticə)

### 4.1 Təsadüfi nümunə (seed=11), siqnal süzgəcisiz
| Platforma | Nümunə | Canlı | Texniki namizəd elan | Qəbul | Məhsuldar lövhə |
|---|---|---|---|---|---|
| Greenhouse | 130 | 113 | 475 | 26 (14 remote, 12 reloc) | 8 (7%) |
| Lever | 90 | 86 | 283 | 2 | 2 (2%) |
| Workable | 60 | 60 | 105 | 0 | 0 |
| Recruitee | 40 | 38 | 72 | 0 | 0 |
| Personio | 40 | 21 (6-sı robots.txt ilə bağlı, 13 mövcud deyil) | 45 | 0 | 0 |
| Teamtailor | 30 | 24 | 21 | 0 | 0 |

Nəticə: Workable/Recruitee/Personio/Teamtailor üçün **təsadüfi slug siyahısı əlavə etməyə dəyməz**. Greenhouse-un bütün siyahısı: 4 785 × 0,88 canlı × 0,23 elan ≈ ~900 qəbul olunan elan inventarı (AI yoxdur).

### 4.2 İki mərhələli süzgəc (Greenhouse 1 327 və Lever 2 174 lövhə süpürüldü)
| | Süpürülən | Canlı | Texniki elanı olan | Remote/Anywhere/Global/EMEA/relocation/visa siqnallı | Siqnallı texniki elan |
|---|---|---|---|---|---|
| Greenhouse | 1 327 (siyahının ~28%-i) | 1 209 | 720 | 274 | 1 249 |
| Lever | 2 174 (siyahının tamamı) | 2 109 | 1 212 | 565 | 6 889 (mətndə relocation/visa sözü də sayılıb, şişkindir) |

2-ci mərhələ (siqnal sayına görə ən güclü lövhələr, qəbul məntiqi):
| | Lövhə | Məhsuldar | Qəbul olunan elan | remote | relocation |
|---|---|---|---|---|---|
| Greenhouse (top 110) | 110 | 28 (25%) | 100 | 84 | 18 |
| Lever (top 70) | 70 | 12 (17%) | 70 | 46 | 24 |

Lövhə tipinə görə: Greenhouse "global siqnallı" (Anywhere/Global/EMEA/Europe) 13 lövhə → 6 məhsuldar, 18 elan, hamısı remote; "sadə Remote" 97 → 22 məhsuldar, 82 elan (18 relocation). Lever global: 10 → 3 məhsuldar, 15 elan; sadə: 60 → 9 məhsuldar, 55 elan.

**Məhsuldar siyahı (təsdiqlənmiş, 50 lövhə). Bütün 871 siqnallı lövhənin (Greenhouse 274 + Lever 565 + ...) siyahısı `docs/source-research-2026-10-signal-boards.json`-dadır:**
- Greenhouse: archer56, etchedai, distantjob, doitintl, clearstreet, axios, stackblitz, axle, atomicindustriesinc, solutions, dyopath, actblue, alpaca, apiphani, ardentmc, clarityinnovates, edb, freenome, censys, amplemarket, bpcs, counterpart, carrotfertility, applytoaktos, greenthumbindustries, customerio, boulevard, array, buzzsolutions, astspacemobile, csciconsulting, altentechnologyusa, assemblyai, brave, soldejaneiro, levelaccess
- Lever: entefy, kepler, allegiantair, metabase, egen, AIFund, Anovium, cscgeneration-2, InfrastructureandCapitalProjects, ans, cgsfederal, agile-defense, diversified-automation, nibiru

**Yüksək güvən (global/EMEA siqnalı, region məhdudiyyəti az ehtimal):** alpaca ("Remote - Global Anywhere"), customerio ("EMEA Remote"), doitintl ("Remote EMEA"), edb ("Remote EMEA"), amplemarket ("Remote, EMEA"), metabase ("Global Remote"), brave ("Anywhere"), nibiru ("Remote - Anywhere"), cscgeneration-2 ("Anywhere"), distantjob, assemblyai, stackblitz, etchedai (relocation).
**ABŞ-məhdudiyyəti riski yüksək (AI/region yoxlaması şərt, ehtimal ki, çox elan düşəcək):** axios, actblue, clearstreet, allegiantair, cgsfederal, agile-defense, kepler, archer56, greenthumbindustries, levelaccess, ans, array.

Qərar: əvvəl yüksək güvənli 13 lövhəni əlavə et, qalanları AI açıq dry-run-dan sonra.

### 4.3 Proqnoz (ehtimal, ölçülməyib)
- Greenhouse siyahısının qalan ~3 500 lövhəsini süpürmək = ~3 500 sorğu (~1 saat, 3–4 paralel, 0,4 s gecikmə) → təxmini ~650 siqnallı lövhə → ~100–170 məhsuldar. Qəbul olunan inventar ~600–1 000 elan, gündəlik yeni **~8–25** (AI/region süzgəci ilə yarıya enə bilər).
- Lever: 565 siqnallı lövhədən ~80–100 məhsuldar, gündə **~3–8**.
- Ashby (bölmə 7) ən böyük əlavə potensial, amma təsdiq gözləyir.
- Rotasiya: qrup başına 12 lövhə/3 saat → 60 lövhəlik qrup ~15 saatda bir dövr tamamlayır; böyük siyahı üçün qrup sayını artırmaq və ya `min_interval_hours`/`max_boards` artırmaq lazım olacaq. `ats.rotation_slots()` testi qrupu bölməyi tələb edir.

## 5. Yeni mənbələr — canlı yoxlanmış namizədlər

Cədvəl sütunları: ad | endpoint/üsul | robots | ToS/açar | sahələr | təxmini qəbul/gün | iş | status.
Qəbul/gün: **M** = dry-run ilə ölçülüb, **E** = ehtimal.

### A. ATS platformaları (yeni tip)
| # | Ad | Endpoint | robots | Açar | Qeydlər | Qəbul/gün | İş |
|---|---|---|---|---|---|---|---|
| 1 | **Workable job aggregator** | `https://jobs.workable.com/api/v1/jobs?query=&location=&workplace=remote&pageToken=` | `Disallow` yalnız `/search*`, `/api/v1/jobs` açıqdır (Content-Signal: ai-train=no) | yox | bütün Workable şirkətləri bir API-də, `workplace`, `location.countryName`, `created`, tam təsvir; **remote elanlar ölkə-başına təkrarlanır** (Texas Sports Academy 1 elan = hər ölkə üçün ayrı sətir). `location=Azerbaijan` 53 elan (28 remote, 9 texniki, **4 qəbul**: CoverGo, Intetics×2, RemoFirst); "relocation/visa" sorğuları: 21 texniki → 4 qəbul (payabl.) | ~0,3–1 (M: 4+4 inventar) | aşağı (1 connector, 2–4 sorğu/saat) |
| 2 | Rippling ATS | `https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs` | api.rippling.com robots 404 (qadağa yox) | yox | siyahı sətirləri: name, department, workLocation.label (yalnız ştat/ölkə kodu); mətn üçün ayrı çağırış lazımdır. Nümunə 40 slug: 36 canlı, 12 texniki, **5 lövhədə siqnal** | ~1–2 (E) | orta |
| 3 | Breezy HR | `https://{slug}.breezy.hr/json` | allow | yox | name, department, `location.is_remote`, `location.name`; nümunə 40: 33 canlı, 12 texniki, 51 texniki elan, **7 lövhədə remote siqnalı (22 elan)** | ~1–3 (E) | aşağı |
| 4 | Pinpoint | `https://{slug}.pinpointhq.com/postings.json` | allow | yox | workplace_type, location, tam təsvir; nümunə 25: 25 canlı, 11 texniki, 47 elan, 8 lövhədə siqnal (hybrid də sayılıb, şişkin) | ~1–2 (E) | aşağı |
| 5 | BambooHR | `https://{slug}.bamboohr.com/careers/list` | allow | yox | siyahıda remote bayrağı seyrək: nümunə 40 → 17 texniki elan, **0 siqnal** | ~0 (M) | — (tövsiyə olunmur) |
| 6 | **Workday CXS** (böyük multinasionallar) | `POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` + detail GET | tenant-dan asılı: nvidia, adobe, autodesk, workday, mastercard, intel, cisco `Allow /{site}/`; zoom, ebay (`Disallow /apply/`) bağlıdır | yox | canlı: nvidia (487 "remote software engineer" nəticə), adobe, autodesk, workday, mastercard, intel, cisco. Hər tenant üçün tenant/shard/site əl ilə lazımdır; "N Locations" siyahıda gizlidir, relocation mətni yalnız detalda | ~2–5 (E) | yüksək |
| 7 | Join.com | company səhifəsi SSR (`__NEXT_DATA__`) | `/companies/` allow, amma jobs sitemap 403 | yox | 23 547 slug, əsasən DACH KOB, çox Alman dilində | ~0–1 (E) | yüksək, aşağı prioritet |
| 8 | Greenhouse genişlənmə | bölmə 4 | allow | yox | — | **~8–25 (E)** | çox aşağı (data) |
| 9 | Lever genişlənmə | bölmə 4 | allow | yox | — | **~3–8 (E)** | çox aşağı (data) |
| 10 | Workable lövhələri (slug) | mövcud connector | allow | yox | 0/60 təsadüfi | ~0 (M) | tövsiyə olunmur |
| 11 | Recruitee (slug) | mövcud | allow | yox | 0/38 | ~0 (M) | tövsiyə olunmur |
| 12 | Personio (slug) | mövcud | 6/40 robots/timeout | yox | 0/21 | ~0 (M) | tövsiyə olunmur |
| 13 | Teamtailor (slug) | mövcud | allow | yox | 0/24 | ~0 (M) | tövsiyə olunmur |

### B. Remote və niş lentlər / API (robots yoxlanıb, `finish_item` dry-run: "aşağı" = remote_default=False, "yuxarı" = remote_default=True)
| # | Ad | Endpoint | robots | Açar | Dry-run (elan/texniki/qəbul aşağı–yuxarı) | Qəbul/gün | Qeyd |
|---|---|---|---|---|---|---|---|
| 14 | **CryptocurrencyJobs.co** | `https://cryptocurrencyjobs.co/index.xml` | allow | yox | 55 / 29 / **14**–26 | ~1–3 (E) | web3, yeni mənbə (Crypto Jobs List-dən fərqli) |
| 15 | **JsJobbs** | `https://jsjobbs.com/rss` | allow | yox | 100 / 72 / 9–60 | ~1–4 (E) | JS/TS, tam mətn |
| 16 | **AI Dev Board** | RSS `https://aidevboard.com/feed.xml`, REST `https://aidevboard.com/api/v1/jobs` (açıq, pulsuz) | allow (`Allow: /`) | opsional | 50 / 46 / 0–15 | ~1–3 (E) | 7 400 AI elanı/417 şirkət, ATS-dən aqreqasiya edir → təkrar riski (URL/şirkət+başlıq dedup) |
| 17 | Startup.jobs RSS | `https://startup.jobs/feeds/jobs` | allow | yox | 50 / 15 / 0–14 | ~0–2 (E) | ən çox ABŞ/ofis; HTML səhifədə Cloudflare ola bilər |
| 18 | JobsInBlockchain | `https://jobsinblockchain.com/rss` | allow | yox | 20 / 11 / 1–2 | ~0–1 | |
| 19 | PyJobs | `https://www.pyjobs.com/rss` | allow | yox | 98 / 81 / 0–81 | ~0–1 (E) | remote siqnalı yoxdur, əsasən ABŞ ofis |
| 20 | ClojureJobboard | `https://clojurejobboard.com/rss.xml` | allow | yox | 4 / 4 / 0–4 | ~0,1 | çox kiçik, niş |
| 21 | LaraJobs | `https://larajobs.com/feed` | allow | yox | 7 / 7 / 0 | ~0 | "US only" üstündür; `job:location` sahəsi var |
| 22 | HN Jobs (YC) | `https://hnrss.org/jobs` | allow | yox | 20 / 12 / 1–10 | ~0,5–1 (E) | YC "is hiring" elanları, ABŞ yönümlü |
| 23 | DOU.ua remote | `https://jobs.dou.ua/vacancies/feeds/?remote` | allow | yox | 25 / 14 / 1–12 | ~0–1 | Ukrayna yönümlü, əksəriyyəti ölkə-məhdud |
| 24 | Werkington | `https://www.werkington.com/feed/` | allow | yox | 10 / 5 / 0–2 | ~0 | texniki az |
| 25 | CV Keskus (Estoniya) | `https://www.cvkeskus.ee/rss-listings.xml` | allow | yox | 23 / 2 / 0 | ~0 | yerli, az texniki |
| 26 | **TokyoDev** | `https://www.tokyodev.com/sitemap.xml` + elan səhifəsində JSON-LD `JobPosting` | allow (`/c/`, `/frames/` bağlı) | yox | 140 elan, 25 nümunənin 7-si viza/relocation sözü içərir (~28%) | ~0,5–1,5 (E) | Yaponiya viza sponsorluğu; mövcud `sitemap.py` ilə |
| 28 | MyCareersFuture (Sinqapur) | `https://api.mycareersfuture.gov.sg/v2/jobs?search=&limit=100&page=` | robots 404 | yox | 1500 / 998 / **0** | 0 (M) | rədd edilir |
| 29 | Getro portfel lövhələri (a16z, Sequoia və s.) | `jobs.a16z.com/sitemap.xml` (688 şirkət səhifəsi) | səhifə allow, **api.getro.com `Disallow: /`** | — | JSON-LD yoxdur, JS ilə render | ~0–1 (E) | çox iş, əsasən ABŞ ofis |

### C. Aqreqator API-lər (açar/razılıq tələb edən)
| # | Ad | Vəziyyət |
|---|---|---|
| 30 | Findwork.dev API | `https://findwork.dev/api/jobs/?remote=true` 401 → pulsuz açar lazımdır; robots allow; texniki, remote filtri var |
| 31 | Adzuna API | `api.adzuna.com` robots `Disallow` → Reed kimi owner istisnası + pulsuz app_id/app_key; ölkə üzrə axtarış |
| 32 | Careerjet partner API | partner/affiliate id tələb edir, endpoint bu şəbəkədən açılmadı |
| 33 | JSearch (RapidAPI) | 401, açar, pulsuz limit çox kiçikdir |
| 34 | Bundesagentur Jobsuche (Almaniya) | `rest.arbeitsagentur.de/...` sənədləşmiş açıq `X-API-Key` ilə də **403** (iki şəbəkədən); server IP-dən yenidən yoxlamaq lazımdır |
| 35 | NAV / Arbeidsplassen (Norveç) | `pam-stilling-feed.nav.no/api/v1/feed` 401, token tələb olunur |
| 36 | Landing.jobs API | JSON işləyir (26 KB), amma **robots `Disallow`** → rəsmi icazə |
| 37 | Remotive API | JSON işləyir, **robots `Disallow`** və 24 saat gecikmə/aqreqator qadağası |
| 38 | Ashby (api.ashbyhq.com) | JSON işləyir (OpenAI lövhəsi), robots 401 → **sizin təsdiqiniz lazımdır**; siyahı: 2 856 (LastRound) / 3 448 (kalil0321) slug. Sayılmır |
| 39 | SmartRecruiters | API işləyir, robots `Disallow` |
| 40 | Gem (jobs.gem.com / api.gem.com) | API Greenhouse-formalı, `api.gem.com/robots.txt` 403; 496 slug; razılıq/yoxlama lazımdır |
| 41 | Comeet | token tələb edir |
| 42 | Workday (tenant-ların robots-u bağlı olanlar) | zoom, ebay və s. |

### D. Yalnız HTML (feed/API yoxdur) — ToS yoxlanmayıb, ən çox iş
| # | Ad | robots (ana səhifə) | Qeyd |
|---|---|---|---|
| 43 | Visasponsor.jobs | allow (Content-Signal ilə) | viza fokuslu, ölkələr üzrə siyahı |
| 44 | EuroTechJobs / EuroEngineerJobs | allow (GPT/Claude botlarına bağlı) | Avropa, relocation sözü çox |
| 45 | EnglishJobs.de | allow | Almaniya ingilis dilli |
| 46 | DevRemote (devremote.io) | allow | Next.js, remote-first şirkətlər |
| 47 | Remote4me / TheRemoteWork / Dynamite Jobs / NoDesk / JustRemote / Remote Rocketship / Arc.dev | allow | remote aqreqatorlar, ən çox təkrar |
| 48 | Levels.fyi jobs | allow | Next.js |
| 49 | WeAreDevelopers | allow | Avropa |
| 50 | Jobs.ge, Bayt, Instahyre, Cutshort, ITviec, TopDev, Kalibrr, DevJobs.se, StartupJobs.cz, Tecnoempleo, Jobs.cz | allow | regional, local-yönlü, aşağı fit |
| 51 | Kube.careers, Embedded.jobs, Mobile.career, ReactNative-jobs, Drupal Jobs, Perl Jobs | allow | niş, həcm çox kiçik |

### E. Rədd edilənlər (səbəb)
NoFluffJobs, JustJoin.it, Authentic Jobs, Vue Jobs, SmartRecruiters (robots); SwissDevJobs, Startup.jobs HTML, RubyOnRemote, Hiring.cafe, Wuzzuf, Pracuj, TheProtocol, Seek, Jobstreet, JobsDB, Naukri, h1bgrader, JobbSafari, Jobbland, CVbankas (Cloudflare/403/bot divarı); GermanTechJobs (qeydiyyata yönləndirir); LinkedIn, Indeed, ZipRecruiter, Glassdoor, Monster (robots/ToS); Stack Overflow Jobs (bağlanıb); DailyRemote (ToS scrape qadağası); Canada Job Bank open data (aylıq dump, təzə deyil); UK/NL/ABŞ sponsor reyestrləri (elan yoxdur, yalnız slug lead); Jobscollider (təkrar); MyCareersFuture (0/998).

## 6. Say
Bölmə 5-də nömrələnmiş sətirlər 51. Bunlardan **yeni və qoşulmağa yararlı (robots+texniki yoxlanıb)**: #1–#4, #6, #8, #9, #14–#16, #17–#26 = **22 mənbə**; açar/razılıq tələb edən: #30–#42 (13); HTML-yalnız: #43–#51 (≈25 sayt qruplanıb); rədd: ≥25. Ümumi yoxlanılmış namizəd ≥ 85 (təkrarlar və mövcudlar çıxıldıqdan sonra).

## 7. Tövsiyə olunan icra sırası
1. **Greenhouse/Lever siqnal-süzgəcli slug genişlənməsi.** Əvvəl 13 yüksək güvənli lövhə, sonra AI-açıq dry-run ilə təsdiq. `sweep` skriptini (1 sorğu/lövhə) bir dəfəlik alət kimi repoya əlavə et, aylıq təkrarla; qalan ~3 500 Greenhouse lövhəsini süpür. Qrup ölçülərini rotasiya üçün böl.
2. **Workable aggregator API** (`location=Azerbaijan`, `workplace=remote`, relocation/visa sorğuları), 2–4 sorğu/saat. Dedup: company+title (ölkə-başına təkrar).
3. **CryptocurrencyJobs.co, JsJobbs, AI Dev Board RSS** (hər biri ~30 sətir connector; AI Dev Board üçün URL dedup).
4. **TokyoDev** (JSON-LD, mövcud sitemap connector).
5. **Breezy, Pinpoint, Rippling** — kiçik, siqnal-süzgəcli slug siyahıları ilə.
6. **Workday CXS** — 8–10 relocation-dostu multinasional (nvidia, adobe, autodesk, workday, mastercard, intel, cisco...), tenant robots-u hər biri üçün yoxla.
7. **Təsdiq/açar:** Ashby robots istisnası (ən böyük potensial), Findwork açarı, Adzuna açarı + robots istisnası, Landing.jobs icazəsi.
8. Bütün bunlardan sonra: `market_purge` yolunda mənbə qaydasının ötürülməsi (əvvəlki qeyd).

## 8. Məhdudiyyətlər
- AI söndürülü: "Remote" + region məhdudiyyəti mətndə yox → bəzi elanlar yalançı qəbul; AI açıq dry-run lazımdır.
- Hər lövhədə namizəd sayı ~15-də kəsilib, ona görə hər lövhənin qəbul sayı aşağı həddir.
- Greenhouse süpürməsi siyahının ~28%-ni əhatə edib (əlifba sırası/direktoriya sırası); proqnoz ekstrapolyasiyadır.
- ToS tam oxunmayıb; robots.txt və açıq API statusu yoxlanıb. HTML-yalnız saytlar ToS baxışı olmadan qoşulmamalıdır.
- Gündəlik rəqəmlər ehtimaldır (inventar/~30 gün), real DB-yə yazılmayıb.
