# Ingress Job

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

Toplayıcı **hər saat** bir keçid edir. Yalnız xarici, uzaqdan iş və ya relokasiya (viza dəstəyi) verən **IT** elanları toplanır: rəsmi API/RSS lentləri (Arbeitnow, Himalayas, Jobicy, Working Nomads, 4 Day Week, HN "Who is hiring", Python.org, Crypto Jobs List və s.) robots.txt-in icazə verdiyi bir neçə sayt (We Work Remotely, Remote OK, Djinni, Wellfound, Relocate.me, Japan Dev, Remote First Jobs), işəgötürənlərin açıq ATS lövhələri regionlar üzrə qruplarla (Greenhouse: Böyük Britaniya və İrlandiya, DACH, Benilüks və Fransa, Skandinaviya və Baltikyanı, Cənubi və Şərqi Avropa, ABŞ qərb, ABŞ şərq, Kanada, Latın Amerikası, Hindistan, Cənub-Şərqi Asiya, Yaponiya və Koreya, Avstraliya və Yeni Zelandiya, Yaxın Şərq və Afrika; Lever: Avropa, Amerika, Hindistan, Asiya-Sakit okean; Teamtailor: Skandinaviya və digər Avropa; Workable, Recruitee, Personio). Şirkət siyahıları `worker/worker/ats_boards.py`-dadır; hər qrup ən çox 3 saatda bir oxunur, bir keçiddə ən çox 12 lövhə (böyük qruplar növbə ilə) və 40 yeni namizəd, remote elanlar əvvəl. və regional açıq mənbələr (İsveç JobTech/Platsbanken API, Latın Amerikası Get on Board API, Hindistan Hasjob, WordPress Jobs, Remote Python). Rusiya mənbələri yoxlanıb: hh.ru API açarsız 403 qaytarır, ona görə "HeadHunter (hh.ru)" `HH_API_KEY` olmadan sönülüdür; Habr Career şərtləri, SuperJob/Trudvsem/Rabota.ru/getmatch robots.txt-i, GeekJob isə açıq lent olmaması səbəbindən toplanmır. Tam siyahı və hər mənbənin qeydi `worker/worker/catalog.py`-dadır. Yerli (Azərbaycan) saytlar 2026-10-05-dən toplanmır; əvvəl toplanmış elanlar silinmir, bir dəfəlik addımla gizlədilir (əməkdaşın "gizlət" bayrağı ilə). Əməkdaş onları toplanmış elanlar siyahısında görür və geri aça bilər. Hər elanın texnologiya siyahısı (`tech_stack`), normallaşdırılmış kateqoriyası (`category`: Backend, Frontend, Full-stack, Mobile, DevOps/Cloud, Data/ML, QA, Security, Design/UX, Product, IT Support, Other tech), `remote` və `relocation` bayraqları saxlanır. Əvvəlcə mənbənin öz kateqoriyası və teqləri istifadə olunur; yoxdursa başlıq və mətn açar sözləri. LinkedIn, Indeed və Tap **toplanmır**. **Jooble** rəsmi API ilə yalnız `JOOBLE_API_KEY` olduqda işləyir (açar yoxdursa keçid atlanır). Açarın limiti cəmi 500 sorğu olduğu üçün Jooble ən çox 6 saatda bir, hər dəfə 3 IT sorğusu (yalnız 1-ci səhifə) ilə çağırılır; sorğular `api_usage` cədvəlində ay üzrə sayılır və ayda 450-yə (`JOOBLE_MONTHLY_BUDGET`) çatanda Jooble daha çağırılmır. **Reed.co.uk** üçün konnektor hazırdır (rəsmi Jobseeker API, `REED_API_KEY` HTTP Basic ilə; ən çox 6 saatda bir, saniyədə 1 sorğu, 5 IT axtarışı, yalnız yeni elanlar üçün detal sorğusu, keçiddə ən çox 30 yeni elan; maaş mənbənin öz valyutası və dövrü ilə (məs. GBP per annum, konvertasiya yoxdur) `salary` sütununa yazılır; sorğular `api_usage`-də ay üzrə sayılır və `REED_MONTHLY_BUDGET`-ə, standart 3000, çatanda dayanır). www.reed.co.uk/robots.txt bütün botlar üçün `Disallow: /api/` yazır; rəsmi açarlı API, istifadəçi təsdiqi ilə istisna edilib (yalnız `https://www.reed.co.uk/api/1.0/`, `worker/worker/http.py` → `ROBOTS_EXCEPTIONS`), saytın qalan hissəsi robots.txt-ə tabedir. Reed yalnız `REED_API_KEY` olduqda işləyir. HeadHunter (hh.ru) **açar olmadan sönülü qalır**: `HH_API_KEY` yoxdursa çağırılmır.

Yeni mənbələri bazaya yazmadan yoxlamaq üçün (müvəqqəti SQLite, hər mənbədən 3 elan):

```bash
cd worker && .venv/bin/python -m worker probe "Himalayas" "Arbeitnow"
```

## Kompüterdə işə salmaq

| Hissə | Port | Ünvan |
|---|---|---|
| Sayt | 3010 | http://localhost:3010 |
| API | 8010 | http://127.0.0.1:8010 |

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

CV faylı `BUCKET_NAME`, `BUCKET_ACCESS_KEY` və `BUCKET_SECRET_KEY` üçünün də olduğu vaxt anbara gedir. Əks halda `api/data` altında qalır və git-ə düşmür.

## Railway

Servislər (`api`, `web`, saatlıq `worker`) və mühit dəyişənlərinin adları: [docs/railway.md](docs/railway.md).

## Qovluqlar

- `frontend` — sayt
- `api` — server
- `worker` — elan toplayıcısı
- `docs` — arxitektura planı və Railway qeydləri
