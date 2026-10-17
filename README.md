# Ingress Job

## 🚀 Layihəni işə salmaq

Hamısı bir əmrlə (API, sayt və saatlıq toplayıcı; loglar `[api]`, `[web]`, `[worker]` etiketləri ilə bir pəncərədə). Dayandırmaq üçün Ctrl+C:

```bash
./scripts/dev.sh
```

Yalnız seçilmiş hissələr:

```bash
./scripts/dev.sh api web
```

Hər hissə ayrıca:

```bash
./scripts/dev-api.sh       # API, http://127.0.0.1:8010
./scripts/dev-web.sh       # sayt, http://localhost:3010
./scripts/dev-worker.sh    # toplayıcı, hər saat bir keçid
```

Toplayıcının yalnız bir keçidi:

```bash
./scripts/dev-worker.sh once
```

**IntelliJ IDEA / PyCharm:** Run siyahısında hazır konfiqurasiyalar var (`.run/` qovluğu): "Ingress Job: API", "Ingress Job: Sayt", "Ingress Job: Toplayıcı", hamısını ayrı tablarda açan "Ingress Job (hamısı)" və hamısını bir pəncərədə açan "Ingress Job: dev.sh (hamısı bir pəncərədə)".

| Hissə | Port | Ünvan |
|---|---|---|
| Sayt | 3010 | http://localhost:3010 |
| API | 8010 | http://127.0.0.1:8010 |

İlk dəfə skriptlər lazım olanı özləri qurur: `.env` (`.env.example`-dan), `api/.venv` və `worker/.venv` (Python 3.12) və `frontend/node_modules`. Bunun üçün kompüterdə `uv` (və ya Python 3.12) və Node.js olmalıdır (`brew install uv node`).

- Port artıq məşğuldursa (məsələn, sayt artıq işləyir), həmin hissə ikinci dəfə başladılmır, sadəcə atlanır.
- Toplayıcı kökdəki `.env`-i oxuyur (`JOOBLE_API_KEY`, `REED_API_KEY` və s.). API isə `api/.env`-i oxuyur; o fayl yoxdursa lokal standart dəyərlər işləyir (nümunə: `api/.env.example`).

Ingress Job iş elanları saytıdır. Şirkət vakansiya yazır, insan elanlara baxır və müraciət edir. Sayt həm də açıq mənbələrdən elan toplayır ki, onlar bir yerdə görünsün.

**Ödəniş yoxdur.** Bu versiyada pul ödəmə, tarif və ya kartla alınma yoxdur.

## Sayt üç dildədir

Azərbaycan, İngilis və Rus. Eyni elanlar və eyni kabinet hər üç dildə açılır. Bir elan bir dildə yazılır: `az`, `en` və ya `ru`.

## Hesabsız nə görmək olar

Elan siyahısına, axtarışa və elanın açıq mətninə **hesab olmadan** baxmaq olar. Qonaq orijinal mənbənin ünvanını görmür.

## Müraciət və orijinal keçid

**Müraciət** və **orijinal elanın keçidi** qeydiyyat istəyir. Hesaba girməyən adam nə müraciət formasını, nə də kənar saytdakı ünvanı görür.

Saytda yazılmış elana müraciət bu saytın forması ilə gedir. Xaricdən toplanmış elanda isə qeydiyyatdan sonra orijinal keçid açılır, bu formaya yox.

## Giriş Academy hesabı ilədir

Ayrı parol yoxdur. İnsan Ingress Academy hesabı ilə daxil olur (OIDC). Job tərəfdən qeydiyyat Academy-yə gedir və qayıdandan sonra rol bu saytda işləyir.

## Şirkət və namizəd

- **Şirkət (işəgötürən)** elan yazır. Əvvəl şirkət adı, şəhər və qısa təsvir saxlanmalıdır. Şirkətin elanı hamıya dərhal düşmür: əməkdaş təsdiq edənə qədər gözləyir (`pending`). Təsdiqdən sonra (`published`) başlıq, mətn, şirkət, şəhər, uzaqdan və ya dil dəyişəndə elan yenidən yoxlamaya düşür. Yalnız əməkhaqqı və iş növü dəyişəndə dərcdə qalır.
- **Namizəd (müraciət edən)** seçilmiş sahələrlə müraciət edir: qısa mətn, CV, telefon, e-poçt və elanı yazanın əlavə sualları. Öz müraciətlərinin statusunu görür: göndərildi, baxıldı, rədd edildi.

## Əməkdaş və moderasiya

**Əməkdaş** elanları yoxlayır. Bu rol saytdakı düymə ilə alınmır, əl ilə verilir. Əməkdaş təsdiq edir, qısa səbəblə rədd edir, bağlayır və sahələri redaktə edir. Rədd edilmiş elan ictimai siyahıda görünmür; sahibi səbəbi görür, düzəldib yenidən göndərə bilər. Bağlanmış elan silinmir, siyahıdan çıxır.

Toplanmış elanlar ayrıca siyahıdadır: mətn redaktəsi, gizlətmə və iki dublikatın birləşdirilməsi. Əl ilə mənbə keçidi (məsələn avtomatik gəlməyən elan) məcburi sahələr və orijinal ünvanla dərhal dərc olunur. Qonaq həmin ünvanı yenə görmür.

## Saatlıq toplama

Toplayıcı **hər saat** bir keçid edir. Yalnız xarici, uzaqdan iş və ya relokasiya (viza dəstəyi) verən **IT** elanları toplanır. Azərbaycan bazarı üçün uzaqdan iş elanı xarici ölkəyə bağlanıbsa (məs. “Remote, Canada”, “US only”) gəlmir; worldwide / EMEA / açıq remote və relokasiya qalır. Mətndə remote/relokasiya/viza siqnalı aydın deyilsə AI dəqiqləşdirir (əvvəl pulsuz providerlər, sonra OpenAI); uyğun deyilsə URL `crawl_rejects`-ə yazılır və növbəti keçiddə AI-siz atılır. Mənbələr: rəsmi API/RSS lentləri (Arbeitnow, Himalayas, Jobicy, Working Nomads, 4 Day Week, HN "Who is hiring", Python.org, Crypto Jobs List və s.), robots.txt-in icazə verdiyi bir neçə sayt (We Work Remotely, Remote OK, Djinni, Wellfound, Relocate.me, Japan Dev, Remote First Jobs), işəgötürənlərin açıq ATS lövhələri regionlar üzrə qruplarla (Greenhouse: Böyük Britaniya və İrlandiya, DACH, Benilüks və Fransa, Skandinaviya və Baltikyanı, Cənubi və Şərqi Avropa, ABŞ qərb, ABŞ şərq, Kanada, Latın Amerikası, Hindistan, Cənub-Şərqi Asiya, Yaponiya və Koreya, Avstraliya və Yeni Zelandiya, Yaxın Şərq və Afrika; Lever: Avropa, Amerika, Hindistan, Asiya-Sakit okean; Teamtailor: Skandinaviya və digər Avropa; Ashby: kripto və Web3, AI/təhlükəsizlik/developer alətləri, Amerika remote; Workable, Recruitee, Personio, Breezy, Pinpoint). Şirkət siyahıları `worker/worker/ats_boards.py` və `worker/worker/ats_boards_extra.py`-dadır; hər qrup ən çox 3 saatda bir oxunur, bir keçiddə ən çox 20 lövhə (böyük qruplar növbə ilə), 200 yeni namizəd (lövhə başına 50) və 150 yeni elan, remote elanlar əvvəl. Regional açıq mənbələr də var (İsveç JobTech/Platsbanken API, Latın Amerikası Get on Board API, Hindistan Hasjob, WordPress Jobs, Remote Python). Rusiya mənbələri yoxlanıb: hh.ru API açarsız 403 qaytarır, ona görə "HeadHunter (hh.ru)" `HH_API_KEY` olmadan sönülüdür; Habr Career şərtləri, SuperJob/Trudvsem/Rabota.ru/getmatch robots.txt-i, GeekJob isə açıq lent olmaması səbəbindən toplanmır. Tam siyahı və hər mənbənin qeydi `worker/worker/catalog.py`-dadır. Yerli (Azərbaycan) saytlar 2026-10-05-dən toplanmır; əvvəl toplanmış elanlar silinmir, bir dəfəlik addımla gizlədilir (əməkdaşın "gizlət" bayrağı ilə). Əməkdaş onları toplanmış elanlar siyahısında görür və geri aça bilər. Hər elanın texnologiya siyahısı (`tech_stack`), normallaşdırılmış kateqoriyası (`category`: Backend, Frontend, Full-stack, Mobile, DevOps/Cloud, Data/ML, QA, Security, Design/UX, Product, IT Support, Other tech), `remote` və `relocation` bayraqları saxlanır. Əvvəlcə mənbənin öz kateqoriyası və teqləri istifadə olunur; yoxdursa başlıq və mətn açar sözləri. LinkedIn, Indeed və Tap **toplanmır**. **Jooble** rəsmi API ilə yalnız `JOOBLE_API_KEY` olduqda işləyir (açar yoxdursa keçid atlanır). Açarın limiti cəmi 500 sorğu olduğu üçün Jooble ən çox 6 saatda bir, hər dəfə 3 IT sorğusu (yalnız 1-ci səhifə) ilə çağırılır; sorğular `api_usage` cədvəlində ay üzrə sayılır və ayda 450-yə (`JOOBLE_MONTHLY_BUDGET`) çatanda Jooble daha çağırılmır. **Reed.co.uk** üçün konnektor hazırdır (rəsmi Jobseeker API, `REED_API_KEY` HTTP Basic ilə; ən çox 6 saatda bir, saniyədə 1 sorğu, 5 IT axtarışı, yalnız yeni elanlar üçün detal sorğusu, keçiddə ən çox 30 yeni elan; maaş mənbənin öz valyutası və dövrü ilə (məs. GBP per annum, konvertasiya yoxdur) `salary` sütununa yazılır; sorğular `api_usage`-də ay üzrə sayılır və `REED_MONTHLY_BUDGET`-ə, standart 3000, çatanda dayanır). www.reed.co.uk/robots.txt bütün botlar üçün `Disallow: /api/` yazır; rəsmi açarlı API, istifadəçi təsdiqi ilə istisna edilib (yalnız `https://www.reed.co.uk/api/1.0/`, `worker/worker/http.py` → `ROBOTS_EXCEPTIONS`), saytın qalan hissəsi robots.txt-ə tabedir. Reed yalnız `REED_API_KEY` olduqda işləyir. HeadHunter (hh.ru) **açar olmadan sönülü qalır**: `HH_API_KEY` yoxdursa çağırılmır.

### Toplama limitləri

Hər keçiddə bir mənbədən ən çox neçə **yeni** elan yazılır (yenilənən və rədd edilən elanlar sayılmır; `worker/worker/limits.py`):

| Səviyyə | Mənbələr | Standart | Dəyişən |
|---|---|---|---|
| api | rəsmi API-lər və ATS lövhələri (Greenhouse, Lever, Ashby, Workable …) | 150 | `MAX_NEW_PER_SOURCE` |
| feed | RSS / JSON lentləri | 100 | `MAX_NEW_PER_SOURCE_FEED` |
| html | elan səhifələri bir-bir oxunan saytlar (Wellfound, Relocate.me, Japan Dev) | 50 | `MAX_NEW_PER_SOURCE_HTML` |

Əvvəl hamısı üçün 30 idi. Mənbənin öz limiti varsa o işləyir (məs. Djinni 300, Himalayas 150). `worker/worker/catalog.py` → `MAX_NEW_OVERRIDES` hamısından üstündür: **Reed.co.uk** və **Jooble** 30-da qalır, çünki aylıq sorğu büdcələri (`REED_MONTHLY_BUDGET`, `JOOBLE_MONTHLY_BUDGET`) buna görə hesablanıb.

Nəzakət limitdən asılı deyil: hər host üçün saniyədə ən çox 1 sorğu (bütün mənbələr arasında bir kilid; Greenhouse-un elan detalı sorğuları da buraya daxildir), robots.txt hər URL üçün yoxlanır, User-Agent `ingress-job-bot/0.1`. Hər mənbənin öz vaxt büdcəsi var (Greenhouse qrupları 600 s, Lever/Teamtailor 300 s, qalanları 600 s, Djinni 1500 s); bütün keçidin də büdcəsi var: `PASS_TIME_BUDGET_SECONDS`, standart 3000 (50 dəqiqə). Bu vaxta qədər başlamayan mənbə növbəti keçidə qalır, işləyən mənbə büdcə bitəndə yazdıqlarını saxlayıb dayanır, beləcə saatlıq keçid növbətisinə qarışmır. Eyni hostdakı mənbələr (məs. Greenhouse qrupları) növbədə bir-birinin ardınca yox, başqa hostlarla qarışıq düzülür.

Əvvəl rədd edilmiş URL-lər (`crawl_rejects`) namizəd seçiləndə atlanır, ona görə köhnə uyğunsuz elanlar yeni elanların yerini tutmur. Ashby elanında işəgötürən maaşı göstəribsə, mətn olduğu kimi (məs. „$160K – $210K • Offers Equity”, konvertasiya yoxdur) `salary`-yə yazılır.

Yeni ATS lövhəsi əlavə etməzdən əvvəl yoxlama (robots.txt, lövhə cavab verir, texniki elan var, qəbul qaydalarından ən azı 1 elan keçir; AI sönülü, iş bazasına toxunmur):

```bash
cd worker && .venv/bin/python scripts/verify_ats_slugs.py --out /tmp/verify.json ashby:supabase lever:offchainlabs
```

SmartRecruiters toplanmır: `api.smartrecruiters.com/robots.txt` LinkedInBot-dan başqa hamıya `Disallow: /` yazır (2026-10-17 yoxlaması). Ashby-nin rəsmi posting-api-si (`api.ashbyhq.com`) oxunmur, çünki onun robots.txt-i HTTP 401 qaytarır; eyni məlumat robots.txt-in icazə verdiyi `jobs.ashbyhq.com` səhifələrindən götürülür.

Yeni mənbələri bazaya yazmadan yoxlamaq üçün (müvəqqəti SQLite, hər mənbədən 3 elan):

```bash
cd worker && .venv/bin/python -m worker probe "Himalayas" "Arbeitnow"
```

Bazadakı toplanmış elanlara bazar qaydalarını yenidən tətbiq etmək (uyğunsuzları gizlət + `crawl_rejects`):

```bash
cd worker && .venv/bin/python -m worker purge-market
```

## Kompüterdə işə salmaq

Ən asan yol yuxarıdakı skriptlərdir ([🚀 Layihəni işə salmaq](#-layihəni-işə-salmaq)). Aşağıdakılar həmin skriptlərin əl ilə ekvivalentidir.

API, `api/` qovluğundan, artıq qurulmuş `api/.venv` ilə:

```bash
cd api
.venv/bin/uvicorn app.main:app --reload --port 8010
```

Sayt:

```bash
cd frontend && npm install && npm run dev
```

Toplayıcı, bir keçid:

```bash
cd worker && .venv/bin/python -m worker
```

Hər saat eyni keçid (`python -m worker schedule`). Proses artıq işləyirsə ikinci keçid açılmır:

```bash
cd worker && .venv/bin/python -m worker schedule
```

`DATABASE_URL` boşdursa elanlar lokal SQLite faylındadır və Postgres şərt deyil. Dəyişən yazılanda API və toplayıcı həmin bazanı bölüşür.

## Mühit dəyişənlərinin adları

Dəyərlər buraya və git-ə yazılmır. Lokal fayl `.env`-dir. Nümunə adlar `.env.example` və `api/.env.example` içindədir.

- `OIDC_ISSUER`
- `OIDC_AUDIENCE`
- `OPENAI_API_KEY`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`
- `SENTRY_DSN`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `BUCKET_NAME`
- `BUCKET_ACCESS_KEY`
- `BUCKET_SECRET_KEY`
- `BUCKET_REGION`
- `BUCKET_ENDPOINT`
- `DATABASE_URL`
- `JOOBLE_API_KEY`
- `REED_API_KEY`
- `HH_API_KEY`
- `MAX_NEW_PER_SOURCE`, `MAX_NEW_PER_SOURCE_FEED`, `MAX_NEW_PER_SOURCE_HTML` (keçiddə mənbə başına yeni elan limiti; boşdursa 150 / 100 / 50)
- `PASS_TIME_BUDGET_SECONDS` (bir keçidin vaxt büdcəsi; boşdursa 3000)

### Park edilmiş səthlər (tövsiyələr / roadmap)

`/me/recommendations` və `/me/insights/roadmap` **default sönülüdür**: menyuda görünmür, URL ana səhifəyə yönləndirilir, əlaqəli API və `coach_weekly` işləmir.

Açmaq üçün API-də:

```bash
PRODUCT_RECOMMENDATIONS_ENABLED=1
PRODUCT_ROADMAP_ENABLED=1
```

Web-də (Next.js):

```bash
NEXT_PUBLIC_PRODUCT_RECOMMENDATIONS_ENABLED=1
NEXT_PUBLIC_PRODUCT_ROADMAP_ENABLED=1
```

Hər iki tərəfi `1` etmədən tam açılmır. Env boş / `0` / `false` / `off` → sönülü qalır.

CV faylı `BUCKET_NAME`, `BUCKET_ACCESS_KEY` və `BUCKET_SECRET_KEY` üçünün də olduğu vaxt anbara gedir. Əks falda `api/data` altında qalır və git-ə düşmür.

## CV üçün OCR (isteğe bağlı)

Skan və ya oxunmaz PDF-lər üçün `tesseract` quraşdırılıbsa OCR avtomatik işləyir, yoxdursa atlanır və `parse_meta.ocr` bunu qeyd edir. Quraşdırma və dəyişənlər: [docs/cv-ocr.md](docs/cv-ocr.md).

## Railway

Servislər (`api`, `web`, saatlıq `worker`) və mühit dəyişənlərinin adları: [docs/railway.md](docs/railway.md).

## Customer journey

Namizəd və işəgötürən səyahət xəritəsi: [docs/customer-journey.md](docs/customer-journey.md).

## Qovluqlar

- `frontend` — sayt
- `api` — server
- `worker` — elan toplayıcısı
- `docs` — arxitektura planı, customer journey və Railway qeydləri
