# Ingress Job – LinkedIn qeyd extension-i

Chrome extension. "Start" basırsınız, LinkedIn-də elanlara özünüz baxırsınız, "Stop" basanda baxdığınız bütün elanlar bir dəfəyə Ingress Job platformasına göndərilir.

**Necə işləyir:** extension yalnız ekranda artıq görünən səhifəni oxuyur (başlıq, şirkət, yer, təsvir, müraciət linki, tarix, iş növü). LinkedIn-ə əlavə sorğu göndərmir, səhifələri özü açmır, heç nəyə klikləmir. Hər elan LinkedIn id-sinə görə bir dəfə saxlanır. "Easy Apply" elanlarında yalnız LinkedIn ünvanı saxlanır.

## 1. API tərəfi (bir dəfəlik)

1. Token yaradın:
   ```bash
   python3 -c "import secrets;print(secrets.token_urlsafe(32))"
   ```
2. API-nin oxuduğu `.env` faylına (məs. `api/.env`; kökdəki `.env`-i skriptlər buna köçürə bilər) əlavə edin:
   ```
   JOB_IMPORT_TOKEN=<yaratdığınız token>
   ```
   Token qoyulmayıbsa endpoint `503` qaytarır. Sonra API-ni yenidən başladın (`./scripts/dev-api.sh`).
3. Endpoint: `POST <sayt>/api/v1/import/linkedin-jobs` (başlıq `X-Import-Token`). API-nin ictimai domeni yoxdur, ona görə extension **saytın (frontend) ünvanına** göndərir; Next.js route (`frontend/app/api/v1/import/linkedin-jobs/route.js`) sorğunu token başlığı ilə API-yə ötürür (`JOB_API_BASE_URL` / lokal `127.0.0.1:8010`). Canlıda `JOB_IMPORT_TOKEN` **API servisində** olmalıdır. Elanlar `linkedin-extension` mənbəsi ilə dərhal dərc olunur və "Toplanmış elanlar" siyahısında görünür. Təkrarlar LinkedIn id və mənbə ünvanına görə atılır.

## 2. Extension-i Chrome-a əlavə etmək

1. Chrome-da `chrome://extensions` açın.
2. Sağ yuxarıda **Developer mode**-u işə salın.
3. **Load unpacked** düyməsinə basın.
4. Bu qovluğu seçin: `/Users/mac/My Workspace/My projects/ingress-job/extension` (içində `manifest.json` var).
5. Puzzle ikonundan extension-i sancaqlayın.

## 3. Ayarlar

Popup-da **Ayarlar** (və ya extension üzərində sağ klik → Options):
- **Sayt ünvanı:** lokal üçün `http://localhost:3010` (default), canlı üçün saytın domeni, məs. `https://sizin-sayt.example` (API ünvanını yox!). Yadda saxlayanda Chrome həmin sayta icazə soruşur, "Allow" edin.
- **Import token:** yuxarıdakı `JOB_IMPORT_TOKEN` dəyəri.

## 4. İstifadə

1. LinkedIn-ə daxil olun.
2. Extension ikonuna basın → **Start** (ikonda qırmızı say görünür).
3. `linkedin.com/jobs` səhifələrində elanlara adi qaydada baxın (axtarış nəticələrində sağdakı detal panelində də işləyir). Elanın təsviri yüklənəndə avtomatik tutulur.
4. Popup-da siyahıya baxın, lazımsızı ✕ ilə silin.
5. **Stop və göndər** basın. Nəticə: yaradıldı / təkrar / xəta. Uğurdan sonra siyahı təmizlənir; bir göndərişdə ən çox 200 elan.

## Qeydlər

- LinkedIn səhifə strukturunu tez-tez dəyişir; boş sahə qalırsa `content.js`-dəki selektorları yeniləmək lazım ola bilər.
- Başlıq və təsvir platformanın limitlərinə qədər kəsilir (başlıq 140, mətn 8000 simvol).
- Xarici müraciət linki varsa orijinal ünvan o olur, yoxsa LinkedIn ünvanı. Qonaqlara bu ünvan göstərilmir.
- Test: `cd api && .venv/bin/python -m unittest tests.test_linkedin_import`
