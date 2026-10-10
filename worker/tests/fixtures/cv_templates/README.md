# CV template text fixtures

Plain-text extracts (pypdf / python-docx output) of 25 public CV templates (15 + 10 below), used by
`tests/test_cv_templates.py`. No binaries are committed. Placeholder / author data
(names, e-mails, phones, handles) was replaced with `example.com` style values.
File name = template id (shared with `worker/cv_parse/templates.py` and
`frontend/lib/cv-styles.js`).

| id | template | source (GitHub) | licence |
| --- | --- | --- | --- |
| vantage_typst | Typst Vantage | sardorml/vantage-typst `example.pdf` | MIT |
| alta_typst | Typst AltaCV | GeorgeHoneywood/alta-typst `example.pdf` | MIT |
| arthur_latex | Arthur CV (LaTeX, date column) | ArthurBernard/Arthur-CV-LaTeX `examples/Arthur_Bernard_CV_En.pdf` | MIT |
| latexcv_classic | latexcv Classic | jankapunkt/latexcv `classic/main.pdf` | MIT |
| latexcv_modern | latexcv Modern | jankapunkt/latexcv `modern/main.pdf` | MIT |
| latexcv_infographics | latexcv Infographics | jankapunkt/latexcv `infographics/main.pdf` | MIT |
| minimal_cv | Minimal-CV | FMatti/Minimal-CV `Minimal-CV.pdf` | MIT |
| academic_xovee | Academic CV | Xovee/latex-cv `cv.pdf` | MIT |
| rover_base | Rover Resume (base) | subidit/rover-resume `templates/base rover/base-rover.pdf` | CC-BY-4.0 |
| rover_fancy | Rover Resume (fancy) | subidit/rover-resume `templates/fancy rover/fancy-rover.pdf` | CC-BY-4.0 |
| chicv | chicv | skyzh/chicv `cv.pdf` | CC0-1.0 |
| simple_resume_cv | simple-resume-cv | zachscrivena/simple-resume-cv `CV.pdf` | Unlicense |
| resumekit_docx | ResumeKit Resume-Template-1 | resumekit/templates `Resume-Template-1.docx` | MIT |
| personal_data_docx | Personal-data CV (DOCX) | blckclov3r/resume `resume.docx` | MIT (personal data replaced) |
| resume_ng_cn | resume-ng (Chinese) | fky2015/resume-ng `main.pdf` | LPPL-1.3c (font without ToUnicode: text is garbled on purpose) |

## Extra batch (generic parser only, no worker detector)

Real-looking sample CVs downloaded earlier; parsed by the generic parser in
`tests/test_cv_templates.py::EXTRA`. Author contact data (names, e-mails, phones, social handles) was replaced
with `example.com` values. Sources/licences were checked against the upstream repositories' LICENSE files
where noted; the RenderCV / Deedy / Awesome-CV / sb2nov licences are stated from the upstream README and
should be re-checked before redistributing anything beyond these short text extracts.

| id | template | source (GitHub) | licence |
| --- | --- | --- | --- |
| rendercv_classic | RenderCV `classic` theme | rendercv/rendercv | MIT |
| rendercv_ember | RenderCV `ember` theme | rendercv/rendercv | MIT |
| rendercv_engres | RenderCV `engineeringresumes` theme | rendercv/rendercv | MIT |
| rendercv_moderncv | RenderCV `moderncv` theme | rendercv/rendercv | MIT |
| deedy_twocol | Deedy Resume (two columns) | deedy/Deedy-Resume | Apache-2.0 |
| awesome_cv | Awesome-CV | posquit0/Awesome-CV | LPPL-1.3c |
| sb2nov_ats | sb2nov resume (ATS) | sb2nov/resume | MIT |
| jobhire_chronological | JobHire Chronological (DOCX) | jobhire-ai/jobhireai-resume-templates | MIT (LICENSE checked) |
| jobhire_modern | JobHire Modern (DOCX) | jobhire-ai/jobhireai-resume-templates | MIT (LICENSE checked) |
| jobhire_twocolumn | JobHire Two-Column (DOCX) | jobhire-ai/jobhireai-resume-templates | MIT (LICENSE checked) |

## Listed in the app but deliberately NOT stored as fixtures

These public files are empty templates (sample / instruction text only: "Job Title", "Month Year",
"year–year", ...). They are not real CVs, so they are not parse fixtures; placeholder handling is tested
with the committed `rover_base` / `chicv` fixtures and inline snippets instead.

| id | template | source (GitHub) | licence |
| --- | --- | --- | --- |
| jobhire_harvard | JobHire Harvard (DOCX) | jobhire-ai/jobhireai-resume-templates | MIT |
| altacv_photo | AltaCV (photo) | liantze/AltaCV | LPPL-1.3c |
| moderncv_casual | moderncv casual | moderncv/moderncv | LPPL-1.3c |
| moderncv_es | moderncv (Español) | moderncv/moderncv | LPPL-1.3c |
| jakujobi | Jakujobi CS Student Resume | jakujobi/Jakujobi-CS-Student-Resume-Template | not stated (NOASSERTION) |
