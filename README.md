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

Toplayıcı **hər saat** bir keçid edir. Yalnız xarici, uzaqdan iş və ya relokasiya (viza dəstəyi) verən **IT** elanları toplanır: rəsmi API/RSS lentləri (Arbeitnow, Himalayas, Jobicy, Working Nomads, 4 Day Week, HN "Who is hiring", Python.org, Crypto Jobs List və s.) və robots.txt-in icazə verdiyi bir neçə sayt (We Work Remotely, Remote OK, Djinni, Wellfound, Relocate.me, Japan Dev, Remote First Jobs). Tam siyahı və hər mənbənin qeydi `worker/worker/catalog.py`-dadır. Yerli (Azərbaycan) saytlar 2026-10-05-dən toplanmır; əvvəl toplanmış elanlar bazada qalır. Hər elanın texnologiya siyahısı (`tech_stack`), `remote` və `relocation` bayraqları saxlanır. LinkedIn, Indeed və Tap **toplanmır**. Jooble və Reed **açar olmadan sönülü qalır**: `JOOBLE_API_KEY` və ya `REED_API_KEY` yoxdursa həmin mənbə çağırılmır.

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

CV faylı `BUCKET_NAME`, `BUCKET_ACCESS_KEY` və `BUCKET_SECRET_KEY` üçünün də olduğu vaxt anbara gedir. Əks halda `api/data` altında qalır və git-ə düşmür.

## Railway

Servislər (`api`, `web`, saatlıq `worker`) və mühit dəyişənlərinin adları: [docs/railway.md](docs/railway.md).

## Qovluqlar

- `frontend` — sayt
- `api` — server
- `worker` — elan toplayıcısı
- `docs` — arxitektura planı və Railway qeydləri
