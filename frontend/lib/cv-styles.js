/**
 * Static CV style cards + the catalogue of known public CV templates.
 *
 * These are *hints for the user* and an optional accuracy boost on the worker side
 * (worker/worker/cv_parse/templates.py shares the template ids). Parsing never
 * depends on them: unknown layouts go through the generic parser and, when the
 * quality score is low, the AI fallback (see cv-quality.js).
 */

const L = (az, en, ru) => ({ az, en, ru });

/** The 5 broad CV styles (always shown). `reading`: how well the generic parser reads them. */
export const CV_STYLES = [
  {
    id: "ats",
    reading: "good",
    name: L("ATS / klassik", "ATS / classic", "ATS / классика"),
    desc: L(
      "Tək sütun, aydın bölmə başlıqları, vəzifə-şirkət-tarix ardıcıllığı.",
      "Single column, clear section headings, title-company-date order.",
      "Одна колонка, чёткие заголовки разделов, порядок должность-компания-дата.",
    ),
    tips: [
      L("Ən yaxşı oxunan üslubdur.", "This is the best-read style.", "Этот стиль читается лучше всего."),
      L("Bölmə adlarını standart saxlayın: Experience, Education, Skills.", "Keep standard headings: Experience, Education, Skills.", "Оставляйте стандартные заголовки: Experience, Education, Skills."),
    ],
  },
  {
    id: "two_column",
    reading: "good",
    name: L("İki sütun", "Two column", "Две колонки"),
    desc: L(
      "Yan panel (əlaqə, bacarıq) və əsas sütun (təcrübə). PDF mətni sütunlar arası qarışa bilər.",
      "Sidebar (contact, skills) plus a main column (experience). PDF text can interleave columns.",
      "Боковая панель (контакты, навыки) и основная колонка (опыт). Текст PDF может перемешиваться.",
    ),
    tips: [
      L("Mətn qatı olan PDF və ya DOCX yükləyin.", "Upload a PDF/DOCX with a text layer.", "Загружайте PDF/DOCX с текстовым слоем."),
      L("Oxunandan sonra iş yerlərinin ardıcıllığını yoxlayın.", "After reading, check the order of jobs.", "После разбора проверьте порядок мест работы."),
    ],
  },
  {
    id: "photo",
    reading: "partial",
    name: L("Foto / dizayn", "Photo / designed", "С фото / дизайнерское"),
    desc: L(
      "Foto, ikonlar və rəngli bloklar. Ikon şrifti mətnə artıq simvol qata bilər.",
      "Photo, icons and coloured blocks. Icon fonts can add stray symbols to the text.",
      "Фото, иконки и цветные блоки. Иконочные шрифты могут добавлять лишние символы.",
    ),
    tips: [
      L("Ad və əlaqə sahələrini əl ilə yoxlayın.", "Check name and contact fields by hand.", "Проверьте имя и контакты вручную."),
      L("Mümkünsə sadə (ikonsuz) variantı da saxlayın.", "Keep a plain (icon-free) version if you can.", "По возможности держите простую версию без иконок."),
    ],
  },
  {
    id: "academic",
    reading: "partial",
    name: L("Akademik", "Academic", "Академическое"),
    desc: L(
      "Uzun nəşr, qrant və mükafat siyahıları; təcrübə 'Appointments' kimi adlana bilər.",
      "Long publication, grant and award lists; experience may be called 'Appointments'.",
      "Длинные списки публикаций, грантов и наград; опыт может называться 'Appointments'.",
    ),
    tips: [
      L("Sənaye təcrübəsini ayrıca 'Experience' bölməsinə yazın.", "Put industry roles in a separate 'Experience' section.", "Выносите работу в индустрии в отдельный раздел 'Experience'."),
      L("Bacarıqlar bölməsi əlavə edin, yoxsa az bacarıq tapılır.", "Add a Skills section or few skills will be found.", "Добавьте раздел Skills, иначе навыков найдётся мало."),
    ],
  },
  {
    id: "creative",
    reading: "partial",
    name: L("Kreativ / infoqrafik", "Creative / infographic", "Креативное / инфографика"),
    desc: L(
      "Qrafik bloklar, bar-lar, fərqli yerləşmə. Tarixlər və başlıqlar çox vaxt ayrı düşür.",
      "Graphic blocks, bars, unusual placement. Dates and titles often end up apart.",
      "Графические блоки, шкалы, нестандартная вёрстка. Даты и должности часто разделяются.",
    ),
    tips: [
      L("Zəif nəticə çıxsa süni intellekt köməyi avtomatik işə düşür.", "On a weak result the AI helper starts automatically.", "При слабом результате автоматически подключается ИИ."),
      L("Formada iş yerlərini əl ilə tamamlayın.", "Complete jobs by hand in the form.", "Дополните места работы вручную в форме."),
    ],
  },
];

/**
 * `reading`: good | partial | sample (the public file is an empty template full of placeholder text,
 * so it cannot be read as a real CV). `worker`: whether worker/cv_parse/templates.py has a detector
 * for it (the "extra" batch is read by the generic parser only).
 */
const T = (id, style, format, name, source, license, reading, desc, tip, worker = true) => ({
  id, style, format, name, source, license, reading, desc, tip, worker,
});
const X = (...args) => T(...args, false);

/** Public templates the parser was tuned on: 15 recognised by the worker (optionally) + 15 generic-parser-only. */
export const CV_TEMPLATES = [
  T("vantage_typst", "ats", "pdf", "Typst Vantage", "github.com/sardorml/vantage-typst", "MIT", "good",
    L("Typst ilə, vəzifə, şirkət və 'YYYY Ay. — YYYY Ay.' tarixləri ayrı sətirlərdə.", "Typst, title / company / 'YYYY Mon. — YYYY Mon.' dates on separate lines.", "Typst: должность, компания и даты 'YYYY Mon. — YYYY Mon.' в отдельных строках."),
    L("Tam oxunur.", "Reads fully.", "Читается полностью.")),
  T("alta_typst", "ats", "pdf", "Typst AltaCV", "github.com/GeorgeHoneywood/alta-typst", "MIT", "good",
    L("Vəzifə, şirkət, sonra tarix və şəhər eyni sətirdə.", "Title, company, then date plus city on one line.", "Должность, компания, затем дата и город в одной строке."),
    L("Şəhər tarixlə eyni sətirdədir, avtomatik ayrılır.", "City shares the date line; it is split off automatically.", "Город в строке с датой; отделяется автоматически.")),
  T("arthur_latex", "photo", "pdf", "Arthur CV (LaTeX)", "github.com/ArthurBernard/Arthur-CV-LaTeX", "MIT", "good",
    L("Solda tarix sütunu, 'Vəzifə at Şirkət' sətri, yan paneldə bacarıqlar.", "Date column on the left, 'Title at Company' line, skills in a sidebar.", "Колонка дат слева, строка 'Title at Company', навыки в боковой панели."),
    L("'Experiences' bölməsi də tanınır.", "The 'Experiences' heading is recognised too.", "Заголовок 'Experiences' тоже распознаётся.")),
  T("latexcv_classic", "ats", "pdf", "latexcv Classic", "github.com/jankapunkt/latexcv", "MIT", "good",
    L("'Vəzifə- Təşkilat YYYY - YYYY' sətri və '·' bullet-ləri.", "'Title- Organisation YYYY - YYYY' line with '·' bullets.", "Строка 'Title- Organisation YYYY - YYYY' и маркеры '·'."),
    L("Rəqəmlər PDF-də şrift adı kimi çıxsa da bərpa olunur.", "Digits that leak as glyph names in the PDF are repaired.", "Цифры, попавшие в PDF как имена глифов, восстанавливаются.")),
  T("latexcv_modern", "two_column", "pdf", "latexcv Modern", "github.com/jankapunkt/latexcv", "MIT", "partial",
    L("Tarix sətrin əvvəlində, vəzifə və şirkət bir sətirdə yapışıb.", "Date at the line start, title and company glued on one line.", "Дата в начале строки, должность и компания слиты в одну."),
    L("Şirkət çox vaxt vəzifəyə qarışır, formada ayırın.", "Company often merges into the title; split it in the form.", "Компания часто сливается с должностью; разделите в форме.")),
  T("latexcv_infographics", "creative", "pdf", "latexcv Infographics", "github.com/jankapunkt/latexcv", "MIT", "partial",
    L("İnfoqrafik bloklar, bar-lar, tarixlər ayrı sütunda.", "Infographic blocks and bars, dates in a separate column.", "Инфографика и шкалы, даты в отдельной колонке."),
    L("Təcrübə tarixləri əl ilə tamamlanmalıdır.", "Job dates usually need manual completion.", "Даты работ обычно нужно дополнять вручную.")),
  T("minimal_cv", "creative", "pdf", "Minimal-CV", "github.com/FMatti/Minimal-CV", "MIT", "partial",
    L("Yan etiketlər (CONTACT, PERSONAL), tarix solda, təşkilat yanında.", "Sidebar labels (CONTACT, PERSONAL), date on the left with the organisation.", "Боковые метки (CONTACT, PERSONAL), дата слева рядом с организацией."),
    L("Vəzifə tarixdən sonrakı sətirdədir.", "The role is on the line after the date.", "Должность на строке после даты.")),
  T("academic_xovee", "academic", "pdf", "Academic CV (Xovee)", "github.com/Xovee/latex-cv", "MIT", "good",
    L("Akademik: Appointments, Distinctions, Publications, ORCID.", "Academic: Appointments, Distinctions, Publications, ORCID.", "Академическое: Appointments, Distinctions, Publications, ORCID."),
    L("'Academic Appointments' təcrübə kimi oxunur.", "'Academic Appointments' is read as experience.", "'Academic Appointments' читается как опыт.")),
  T("rover_base", "ats", "pdf", "Rover Resume (base)", "github.com/subidit/rover-resume", "CC-BY-4.0", "partial",
    L("Tək sütun, 'Şirkət Şəhər' və 'Vəzifə Ay İl - Ay İl' sətirləri.", "Single column, 'Company City' and 'Position Month Year - Month Year' lines.", "Одна колонка, строки 'Company City' и 'Position Month Year - Month Year'."),
    L("Nümunə mətnlə (Month Year) deyil, real tarixlərlə yazın.", "Fill with real dates, not the sample 'Month Year'.", "Пишите реальные даты, а не образец 'Month Year'.")),
  T("rover_fancy", "photo", "pdf", "Rover Resume (fancy)", "github.com/subidit/rover-resume", "CC-BY-4.0", "good",
    L("Başlıqda ikonlu əlaqə sətri, şirkət və tarix bir sətirdə.", "Header contact line with icons, company and date on one line.", "Строка контактов с иконками, компания и дата в одной строке."),
    L("İkon simvolları təmizlənir, əlaqəni yoxlayın.", "Icon glyphs are stripped; double-check the contacts.", "Символы иконок удаляются; проверьте контакты.")),
  T("chicv", "ats", "pdf", "chicv (Typst)", "github.com/skyzh/chicv", "CC0-1.0", "partial",
    L("Tək sütun, tarixlər 'YYYY/MM – YYYY/MM' formatında.", "Single column, dates as 'YYYY/MM – YYYY/MM'.", "Одна колонка, даты в формате 'YYYY/MM – YYYY/MM'."),
    L("Nümunə (Lorem ipsum) mətnini real məlumatla əvəz edin.", "Replace the Lorem ipsum sample with real data.", "Замените образец Lorem ipsum реальными данными.")),
  T("simple_resume_cv", "academic", "pdf", "simple-resume-cv (LaTeX)", "github.com/zachscrivena/simple-resume-cv", "Unlicense", "good",
    L("'■' ilə vəzifə sətri, '●' alt bəndlər, bölmə adı mətnlə eyni sətirdə.", "'■' role lines, '●' sub-bullets, section names sharing a line with content.", "Строки должностей с '■', подпункты '●', заголовки в одной строке с текстом."),
    L("'EDUCATION ...' kimi birləşik başlıqlar ayrılır.", "Joined headings such as 'EDUCATION ...' are split.", "Слитые заголовки вроде 'EDUCATION ...' разделяются.")),
  T("resumekit_docx", "ats", "docx", "ResumeKit (DOCX)", "github.com/resumekit/templates", "MIT", "good",
    L("DOCX, 'Vəzifə at Şirkət, Ay İl - till date' sətirləri.", "DOCX, 'Title at Company, Month Year - till date' lines.", "DOCX, строки 'Title at Company, Month Year - till date'."),
    L("Ad bölməsi yoxdursa, Ad sahəsini əl ilə doldurun.", "If there is no name block, fill the Name field by hand.", "Если нет блока с именем, заполните имя вручную.")),
  T("personal_data_docx", "ats", "docx", "Personal-data CV (DOCX)", "github.com/blckclov3r/resume", "MIT", "good",
    L("DOCX, 'PERSONAL DATA' və 'CAREER OBJECTIVE', 'Ay İl | Ay İl' tarixləri.", "DOCX, 'PERSONAL DATA' and 'CAREER OBJECTIVE', dates like 'Month Year | Month Year'.", "DOCX, 'PERSONAL DATA' и 'CAREER OBJECTIVE', даты вида 'Month Year | Month Year'."),
    L("Doğum tarixi kimi şəxsi sahələr profilə köçürülmür.", "Personal fields such as birth date are not copied to the profile.", "Личные поля вроде даты рождения в профиль не переносятся.")),
  T("resume_ng_cn", "creative", "pdf", "resume-ng (Chinese LaTeX)", "github.com/fky2015/resume-ng", "LPPL-1.3c", "partial",
    L("Şrifti mətnə çevrilməyən PDF: simvollar oxunmur.", "PDF whose font has no text mapping: glyphs are unreadable.", "PDF со шрифтом без карты текста: символы нечитаемы."),
    L("OCR yoxdursa mətn oxunmur; DOCX və ya başqa PDF yükləyin.", "Without OCR the text is unreadable; upload a DOCX or another PDF.", "Без OCR текст нечитаем; загрузите DOCX или другой PDF.")),

  // --- Extra batch (earlier /tmp/cvs set): read by the generic parser, no worker detector. ---
  X("rendercv_classic", "ats", "pdf", "RenderCV Classic", "github.com/rendercv/rendercv", "MIT", "good",
    L("YAML-dan yaradılan tək sütunlu PDF, bölmə başlıqları və tarixlər aydındır.", "Single-column PDF generated from YAML, clear headings and dates.", "Одноколоночный PDF из YAML, чёткие заголовки и даты."),
    L("Tam oxunur.", "Reads fully.", "Читается полностью.")),
  X("rendercv_ember", "ats", "pdf", "RenderCV Ember", "github.com/rendercv/rendercv", "MIT", "good",
    L("RenderCV-nin 'ember' mövzusu: tək sütun, ortada başlıq.", "RenderCV 'ember' theme: single column, centred header.", "Тема 'ember' RenderCV: одна колонка, центрированная шапка."),
    L("Tam oxunur.", "Reads fully.", "Читается полностью.")),
  X("rendercv_engres", "ats", "pdf", "RenderCV Engineering Resumes", "github.com/rendercv/rendercv", "MIT", "good",
    L("'engineeringresumes' mövzusu: sıx tək sütun, '|' ilə əlaqə sətri.", "'engineeringresumes' theme: dense single column, contacts joined with '|'.", "Тема 'engineeringresumes': плотная одна колонка, контакты через '|'."),
    L("Tam oxunur.", "Reads fully.", "Читается полностью.")),
  X("rendercv_moderncv", "ats", "pdf", "RenderCV ModernCV theme", "github.com/rendercv/rendercv", "MIT", "good",
    L("'moderncv' mövzusu: solda tarix sütunu, sağda təsvir.", "'moderncv' theme: date column on the left, description on the right.", "Тема 'moderncv': колонка дат слева, описание справа."),
    L("Tam oxunur.", "Reads fully.", "Читается полностью.")),
  X("deedy_twocol", "two_column", "pdf", "Deedy Resume (two columns)", "github.com/deedy/Deedy-Resume", "Apache-2.0", "good",
    L("Sıx iki sütun: solda təhsil, bacarıq; sağda təcrübə. VƏZİFƏ və ŞİRKƏT böyük hərflə.", "Dense two columns: education and skills left, experience right. TITLE and COMPANY in capitals.", "Плотные две колонки: слева образование и навыки, справа опыт. Должность и компания заглавными."),
    L("Böyük hərfli başlıqlar tanınır.", "Capitalised headings are recognised.", "Заголовки заглавными распознаются.")),
  X("awesome_cv", "photo", "pdf", "Awesome-CV", "github.com/posquit0/Awesome-CV", "LPPL-1.3c", "partial",
    L("Dizayn edilmiş LaTeX: ikonlu əlaqə sətri, rəngli başlıqlar, tarix sağda.", "Designed LaTeX: icon contact line, coloured headings, dates on the right.", "Дизайнерский LaTeX: контакты с иконками, цветные заголовки, даты справа."),
    L("PDF-də sözlər arası boşluq itə bilər; ad və əlaqəni yoxlayın.", "The PDF can lose spaces between words; check name and contacts.", "В PDF могут пропадать пробелы между словами; проверьте имя и контакты.")),
  X("sb2nov_ats", "ats", "pdf", "sb2nov resume (ATS)", "github.com/sb2nov/resume", "MIT", "good",
    L("Məşhur ATS LaTeX şablonu: '•' ilə başlıqlar, şirkət və şəhər eyni sətirdə.", "Popular ATS LaTeX template: '•' headings, company and city on one line.", "Популярный ATS-шаблон LaTeX: заголовки с '•', компания и город в одной строке."),
    L("Şəhər bəzən şirkət adına qarışır.", "The city sometimes merges into the company name.", "Город иногда сливается с названием компании.")),
  X("jobhire_chronological", "ats", "docx", "JobHire Chronological", "github.com/jobhire-ai/jobhireai-resume-templates", "MIT", "good",
    L("DOCX, xronoloji: əlaqə ikonları, vəzifə və şirkət ayrı sətirlərdə.", "DOCX, chronological: contact icons, title and company on separate lines.", "DOCX, хронологический: иконки контактов, должность и компания в разных строках."),
    L("Bacarıqlar bölməsi qısa ola bilər; əlavə edin.", "The skills section may be short; add more.", "Раздел навыков может быть коротким; дополните.")),
  X("jobhire_harvard", "ats", "docx", "JobHire Harvard", "github.com/jobhire-ai/jobhireai-resume-templates", "MIT", "sample",
    L("DOCX, Harvard üslubu. Fayl boş şablondur (Job Title, Month Year, City, State).", "DOCX, Harvard style. The file is an empty template (Job Title, Month Year, City, State).", "DOCX, стиль Harvard. Файл пустой шаблон (Job Title, Month Year, City, State)."),
    L("Nümunə mətni real məlumatla əvəz edin; yoxsa AI köməyə çağırılır.", "Replace the sample text with real data; otherwise the AI helper is called.", "Замените образец реальными данными; иначе подключается ИИ.")),
  X("jobhire_modern", "photo", "docx", "JobHire Modern", "github.com/jobhire-ai/jobhireai-resume-templates", "MIT", "good",
    L("DOCX, müasir: başlıq, ikonlu əlaqə və qısa təcrübə siyahısı.", "DOCX, modern: headline, icon contacts and a short experience list.", "DOCX, современный: заголовок, контакты с иконками и короткий список опыта."),
    L("Bacarıqlar bölməsi qısa ola bilər.", "The skills section may be short.", "Раздел навыков может быть коротким.")),
  X("jobhire_twocolumn", "two_column", "docx", "JobHire Two-Column", "github.com/jobhire-ai/jobhireai-resume-templates", "MIT", "good",
    L("DOCX, iki sütun (cədvəl): yan paneldə əlaqə və bacarıq.", "DOCX, two columns (table): contact and skills in the sidebar.", "DOCX, две колонки (таблица): контакты и навыки в боковой панели."),
    L("Cədvəl mətni oxunur; bacarıqları yoxlayın.", "Table text is read; check the skills.", "Текст таблицы читается; проверьте навыки.")),
  X("altacv_photo", "photo", "pdf", "AltaCV (photo, LaTeX)", "github.com/liantze/AltaCV", "LPPL-1.3c", "sample",
    L("Fotolu kreativ LaTeX şablonu; PDF nümunə mətn və ikon simvolları ilə doludur.", "Creative LaTeX template with a photo; the PDF holds sample text and icon glyphs.", "Креативный LaTeX-шаблон с фото; в PDF образец текста и символы иконок."),
    L("Təcrübə bölməsi tanınmır; AI köməyə çağırılır.", "The experience section is not recognised; the AI helper steps in.", "Раздел опыта не распознаётся; подключается ИИ.")),
  X("moderncv_casual", "academic", "pdf", "moderncv (casual)", "github.com/moderncv/moderncv", "LPPL-1.3c", "sample",
    L("LaTeX moderncv, 'year–year' tarixləri; fayl nümunə mətndir.", "LaTeX moderncv with 'year–year' dates; the file is sample text.", "LaTeX moderncv с датами 'year–year'; файл образец текста."),
    L("Real məlumatla doldurulduqda yaxşı oxunur.", "Reads well once filled with real data.", "Читается хорошо после заполнения реальными данными.")),
  X("moderncv_es", "academic", "pdf", "moderncv (Español)", "github.com/moderncv/moderncv", "LPPL-1.3c", "sample",
    L("moderncv-nin ispan nümunəsi ('año–año', 'Experiencia'); fayl nümunə mətndir.", "Spanish moderncv sample ('año–año', 'Experiencia'); the file is sample text.", "Испанский образец moderncv ('año–año', 'Experiencia'); файл образец текста."),
    L("İspan başlıqları üçün AI köməyi lazım ola bilər.", "Spanish headings may need the AI helper.", "Для испанских заголовков может понадобиться ИИ.")),
  X("jakujobi", "ats", "docx", "Jakujobi CS Student", "github.com/jakujobi/Jakujobi-CS-Student-Resume-Template", "not stated", "sample",
    L("DOCX, tələbə/təcrübəçi üçün; fayl izahat mətnləri ilə doludur.", "DOCX for students and interns; the file is full of instruction text.", "DOCX для студентов и стажёров; файл полон поясняющего текста."),
    L("Izahatları silib real məlumat yazın.", "Delete the instructions and write real data.", "Удалите пояснения и впишите реальные данные.")),
];

export const pick = (value, locale) => (value && (value[locale] || value.en)) || "";

export const styleById = (id) => CV_STYLES.find((s) => s.id === id) || null;
export const templateById = (id) => CV_TEMPLATES.find((t) => t.id === id) || null;
export const templatesByStyle = (styleId) => CV_TEMPLATES.filter((t) => t.style === styleId);

/**
 * Detected template from profile.parse_meta.template (written by the worker).
 * Returns null when the profile has no template info (old profiles), and
 * `{ id: null }` when detection ran but found no known template.
 */
export function detectedTemplate(meta) {
  const tpl = meta && typeof meta === "object" ? meta.template : null;
  if (!tpl || typeof tpl !== "object") return null;
  if (!tpl.id) return { id: null, entry: null, style: null, applied: false, confidence: null };
  const entry = templateById(tpl.id);
  return {
    id: String(tpl.id),
    name: String(tpl.name || entry?.name || tpl.id),
    entry,
    style: entry ? styleById(entry.style) : null,
    applied: Boolean(tpl.applied),
    confidence: typeof tpl.confidence === "number" ? Math.max(0, Math.min(1, tpl.confidence)) : null,
  };
}
