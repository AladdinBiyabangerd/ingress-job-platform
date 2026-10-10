# CV üçün isteğe bağlı OCR (tesseract)

CV parse-ı əvvəl PDF/DOCX-in mətn qatını oxuyur. OCR **yalnız** bu hallarda işə düşür:

- PDF-də mətn qatı yoxdur və ya çox azdır (skan),
- mətn qatı oxunmazdır (şrift xəritəsi yoxdur, `text_garbled`, məs. resume-ng PDF-i),
- yüklənən fayl şəkildir (PNG/JPG/TIFF/WebP/GIF).

OCR qurulmayıbsa heç nə sınmır: parse davam edir, nəticə `parse_meta.ocr` sahəsində qeyd olunur.

## `parse_meta.ocr`

OCR lazım olmayanda (adi rəqəmsal PDF/DOCX) bu sahə yoxdur. Lazım olanda:

| `status` | məna |
| --- | --- |
| `used` | OCR mətni çıxardı və parse ondan getdi |
| `unavailable` | OCR lazım idi, amma `tesseract` binary-si və ya Python paketi yoxdur (`reason`: `tesseract_missing`, `python_dep_missing:<paket>`) |
| `disabled` | `CV_OCR_ENABLED=0` |
| `empty` | OCR işlədi, amma oxunaqlı mətn çıxmadı |

`text_garbled` olan PDF-də OCR nəticə verməsə, köhnə (oxunmaz) mətn və `text_garbled` xətası saxlanır, AI çağırılmır.

## Necə aktiv etmək

Python paketləri (`pytesseract`, `pypdfium2`, `Pillow`) `worker/pyproject.toml`-dadır. Sistem binary-si lazımdır:

- **Docker (Railway):** `worker/Dockerfile` və `api/Dockerfile` artıq `tesseract-ocr` quraşdırır və `CV_OCR_ENABLED=1`, `CV_OCR_LANG=eng` qoyur. Əlavə dil üçün Dockerfile-da `tesseract-ocr-rus` və ya `tesseract-ocr-aze` əlavə edin və `CV_OCR_LANG=eng+rus` yazın.
- **macOS:** `brew install tesseract` (rus/azərbaycan üçün `brew install tesseract-lang`).
- **Debian/Ubuntu:** `sudo apt-get install tesseract-ocr`.

Yoxlama: `tesseract --version`, sonra worker-i yenidən başladın (yoxlama nəticəsi prosesdə keşlənir).

## Mühit dəyişənləri

| dəyişən | default | təsvir |
| --- | --- | --- |
| `CV_OCR_ENABLED` | `1` | `0` / `false` / `off` OCR-ı söndürür |
| `CV_OCR_LANG` | `eng` | tesseract dilləri, məs. `eng+rus` |
| `CV_OCR_SCALE` | `2.0` | PDF səhifəsinin render miqyası (1–4) |

Bir CV-də ən çox 15 səhifə OCR olunur.
