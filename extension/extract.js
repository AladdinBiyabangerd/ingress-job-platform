// LinkedIn iş elanı səhifəsini passiv oxuyan saf funksiyalar (şəbəkə yoxdur).
// Brauzerdə globalThis.IJExtract, Node-da module.exports kimi açılır.
(function (root) {
  const lc = (s) => String(s || "").toLocaleLowerCase("tr");
  const clean = (s) => String(s || "").replace(/[ \t\u00a0]+/g, " ").replace(/\s*\n\s*/g, "\n").trim();
  const text = (el) => (el ? clean(el.innerText !== undefined ? el.innerText : el.textContent) : "");
  // innerText görünən (kəsilmiş) mətn; textContent gizli tam mətni də götürə bilər — uzunu seç.
  const richText = (el) => {
    if (!el) return "";
    const a = clean(el.innerText !== undefined ? el.innerText : "");
    const b = clean(el.textContent || "");
    return a.length >= b.length ? a : b;
  };

  // Çoxdilli başlıqlar / etiketlər (en, tr, az, ru, de, fr, es)
  const ABOUT_JOB = /^(about the job|job description|iş ilanı hakkında|iş tanımı|vakansiya haqqında|elan haqqında|iş elanı haqqında|о вакансии|описание вакансии|über die stelle|stellenbeschreibung|à propos de l.offre|description du poste|acerca del empleo|información sobre el empleo)$/;
  const ABOUT_COMPANY = /^(about the company|about us|şirket hakkında|şirkət haqqında|şirkət barədə|о компании|über das unternehmen|à propos de l.entreprise|acerca de la empresa)$/;
  // Təsvirin sonu: Premium təklifi və ya şirkət bölməsi (daxili başlıqlara ("Requirements" və s.) güvənmirik)
  const END_BLOCK = /^(job search faster with premium|get hired faster with premium|try premium|reactivate premium|retry premium|see how you compare|premium ile|premium ilə|premium ile daha hızlı|попробуйте premium|ищите работу быстрее с premium)/;
  // Təsvirə aid olmayan LinkedIn interfeys sətirləri
  const NOISE = /^(your profile and resume are missing|profiliniz ve özgeçmişiniz|show match details|eşleşme ayrıntılarını göster|beta\b|is this information helpful|bu bilgi yararlı mı|see how you compare|tailor my resume|resume builder|job match summary not available|this job post doesn.t have enough information|responses managed off linkedin|show more|show less|see more|see less|read more|daha fazla göster|daha az göster|daha fazla|daha çox|\d+\+? (people|applicants|kişi)|over \d+ (applicants|people)|\d+ (applicants|kişi))/;
  const SHOW_MORE = /(show more|see more|read more|daha fazla|daha çox|voir plus|ver más|siehe mehr|показать ещё|показать еще|ещё|еще)/;
  const SHOW_LESS = /(show less|see less|daha az|voir moins|ver menos|weniger|скрыть|свернуть)/;
  const EASY = /(easy apply|kolay başvuru|asan müraciət|быстрая подача|candidature simplifiée|solicitud sencilla|einfach bewerben)/;
  const APPLY = /(^|\s)(apply|başvur|müraciət|подать|откликнуться|bewerben|postuler|candidatar|solicitar)/;
  const REMOTE = /^(remote|uzaktan|uzaqdan|удал[её]нно|удал[её]нная работа|fernarbeit|à distance|remoto)$/;
  const WORKPLACE = /^(remote|on-site|onsite|hybrid|uzaktan|uzaqdan|hibrit|hibrid|iş yerinde|ofisdə|ofis|удал[её]нно|гибрид|в офисе|vor ort|présentiel|presencial|remoto|à distance)$/;
  const EMPLOYMENT = /^(full-time|part-time|contract|temporary|internship|volunteer|freelance|apprenticeship|tam zamanlı|yarı zamanlı|sözleşmeli|geçici|staj|gönüllü|serbest|tam ştat|yarım ştat|müqavilə|müvəqqəti|təcrübə|полная занятость|частичная занятость|контракт|временная|стажировка|vollzeit|teilzeit|temps plein|temps partiel|tiempo completo|media jornada)$/;

  function jobIdFromUrl(href) {
    try {
      const u = new URL(href, "https://www.linkedin.com");
      const q = u.searchParams.get("currentJobId");
      if (q && /^\d+$/.test(q)) return q;
      const m = u.pathname.match(/\/jobs\/view\/(?:[^/?#]*?-)?(\d{5,})/);
      return m ? m[1] : "";
    } catch (_) {
      return "";
    }
  }

  // linkedin.com/safety/go/?url=<kodlanmış> -> real xarici ünvan (utm_* təmizlənir)
  function decodeApplyUrl(href, base) {
    if (!href) return "";
    try {
      const u = new URL(href, base || "https://www.linkedin.com");
      let target = u.href;
      if (/(^|\.)linkedin\.com$/.test(u.hostname)) {
        if (!/^\/(safety\/go|redir\/redirect|jobs\/apply-redirect)/.test(u.pathname)) return "";
        target = u.searchParams.get("url") || u.searchParams.get("dest") || "";
        if (!target) return "";
      }
      const t = new URL(target);
      if (!/^https?:$/.test(t.protocol) || /(^|\.)linkedin\.com$/.test(t.hostname)) return "";
      [...t.searchParams.keys()].filter((k) => /^utm_/i.test(k)).forEach((k) => t.searchParams.delete(k));
      return t.href;
    } catch (_) {
      return "";
    }
  }

  function jsonLd(doc) {
    for (const s of doc.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const d = JSON.parse(s.textContent);
        for (const x of Array.isArray(d) ? d : [d]) if (x && x["@type"] === "JobPosting") return x;
      } catch (_) {}
    }
    return null;
  }

  function findHeading(doc, re) {
    const nodes = doc.querySelectorAll("h1,h2,h3,h4,h5,span,strong,p,div,b");
    for (const n of nodes) {
      if (n.children.length > 1) continue;
      const t = lc(text(n)).replace(/[:：]$/, "");
      if (t && t.length < 60 && re.test(t)) return n;
    }
    return null;
  }

  function descriptionRoot(doc) {
    return doc.querySelector(
      '#job-details, .jobs-description__content, .jobs-box__html-content, .jobs-description, [data-testid="expandable-text-box"], [componentkey*="AboutTheJob" i]'
    );
  }

  // Qeyd zamanı yalnız təsvirin "Show more" düyməsi (elanlar arası keçid / Apply yox).
  function findShowMore(doc) {
    const root = descriptionRoot(doc) || findHeading(doc, ABOUT_JOB)?.closest("section,article,div") || null;
    if (!root) return null;
    for (const btn of root.querySelectorAll('button, a[role="button"], span[role="button"]')) {
      if (btn.getAttribute("aria-expanded") === "true") continue;
      const label = lc(btn.getAttribute("aria-label") || text(btn));
      if (!label || SHOW_LESS.test(label) || !SHOW_MORE.test(label)) continue;
      return btn;
    }
    return null;
  }

  function descriptionOf(doc) {
    const direct = descriptionRoot(doc);
    if (direct && richText(direct).length > 40) {
      return { desc: stripHeadings(richText(direct)), heading: findHeading(doc, ABOUT_JOB) };
    }
    const h = findHeading(doc, ABOUT_JOB);
    if (!h) return { desc: "", heading: null };
    // Başlığın qardaş elementlərindəki mətn (təsvir); yetərli deyilsə bir səviyyə yuxarı çıx.
    let el = h;
    for (let i = 0; i < 8 && el && el !== doc.body; i++) {
      const parts = [];
      for (let sib = el.nextElementSibling; sib; sib = sib.nextElementSibling) {
        const t = richText(sib);
        if (!t) continue;
        const first = lc(t.split("\n")[0]).replace(/[:：]$/, "");
        if (ABOUT_COMPANY.test(first) || END_BLOCK.test(first) || findHeading(sib, ABOUT_COMPANY)) break;
        parts.push(t);
      }
      const joined = parts.join("\n");
      if (joined.length >= 40) return { desc: stripHeadings(joined), heading: h };
      el = el.parentElement;
    }
    return { desc: "", heading: h };
  }

  function descriptionFromLd(doc, ld) {
    if (!ld || !ld.description) return "";
    const d = doc.createElement("div");
    d.innerHTML = ld.description;
    return stripHeadings(richText(d) || text(d));
  }

  function stripHeadings(t) {
    const out = [];
    for (const line of t.split("\n")) {
      const l = lc(line).trim().replace(/[:：]$/, "");
      if (ABOUT_COMPANY.test(l) || END_BLOCK.test(l)) break;
      if (ABOUT_JOB.test(l) && !out.length) continue;
      if (NOISE.test(l)) continue;
      out.push(line);
    }
    return out.join("\n").trim();
  }

  function scopeOf(doc, heading) {
    let el = heading;
    while (el && el !== doc.body) {
      if (el.querySelector && el.querySelector('a[href*="/company/"]')) return el;
      el = el.parentElement;
    }
    return doc;
  }

  function locationLine(scope) {
    let fallback = [];
    for (const n of scope.querySelectorAll("p,span,div")) {
      const t = text(n);
      if (!t || t.length > 220 || t.includes("\n") || !t.includes("·")) continue;
      if (n.querySelector("p,div")) continue;
      const parts = t.split("·").map((x) => x.trim());
      if (/\d/.test(parts[1] || "")) return parts; // "Yer · 1 hafta önce · ..."
      if (!fallback.length) fallback = parts;
    }
    return fallback;
  }

  function chips(scope) {
    const out = [];
    for (const n of scope.querySelectorAll("button,span,li,a,div")) {
      if (n.children.length > 1) continue;
      const t = text(n);
      if (t && t.length <= 30 && !t.includes("\n")) out.push(t);
    }
    return out;
  }

  function findApply(scope, base) {
    const anchors = [...scope.querySelectorAll("a[href]")];
    for (const a of anchors) {
      if (/\/safety\/go|\/redir\/redirect|apply-redirect/.test(a.getAttribute("href") || "")) {
        const url = decodeApplyUrl(a.getAttribute("href"), base);
        if (url) return url;
      }
    }
    for (const a of anchors) {
      const label = lc(a.getAttribute("aria-label") || text(a));
      if (EASY.test(label) || !APPLY.test(label)) continue;
      const url = decodeApplyUrl(a.getAttribute("href"), base);
      if (url) return url;
    }
    return "";
  }

  function extract(doc, href) {
    const id = jobIdFromUrl(href);
    if (!id) return null;
    const ld = jsonLd(doc);
    const { desc, heading } = descriptionOf(doc);
    const scope = heading ? scopeOf(doc, heading) : doc;
    const titleParts = (doc.title || "").split(/\s[|–-]\s/).map((s) => s.trim());

    let title = "";
    for (const a of scope.querySelectorAll(`a[href*="/jobs/view/${id}"]`)) {
      const t = text(a).split("\n")[0].trim();
      if (t) { title = t; break; }
    }
    if (!title) {
      const h1 = scope.querySelector("h1") || doc.querySelector("h1");
      if (h1) title = text(h1).split("\n")[0].trim();
    }
    title = title || (ld && ld.title) || titleParts[0] || "";

    let company = "";
    for (const a of scope.querySelectorAll('a[href*="/company/"]')) {
      const t = text(a);
      if (t) { company = t.split("\n")[0]; break; }
    }
    company = company || (ld && ld.hiringOrganization && ld.hiringOrganization.name) || "";

    const line = locationLine(scope);
    let loc = line[0] || "";
    let posted = line[1] && /\d/.test(line[1]) ? line[1] : "";
    if (ld) {
      const a = ld.jobLocation && ld.jobLocation.address;
      loc = loc || (a ? [a.addressLocality, a.addressCountry && (a.addressCountry.name || a.addressCountry)].filter(Boolean).join(", ") : "");
      posted = posted || ld.datePosted || "";
    }

    const labels = chips(scope);
    const workplace = labels.find((t) => WORKPLACE.test(lc(t))) || "";
    const employment = labels.find((t) => EMPLOYMENT.test(lc(t))) || (ld && (Array.isArray(ld.employmentType) ? ld.employmentType[0] : ld.employmentType)) || "";

    let description = desc;
    const fromLd = descriptionFromLd(doc, ld);
    if (fromLd.length > description.length) description = fromLd;

    if (!title) return null;
    return {
      linkedin_id: id,
      title,
      company,
      location: loc,
      description,
      // Xarici link yoxdursa (Easy Apply / Kolay Başvuru) LinkedIn elan ünvanı müraciət linki olur.
      apply_url: findApply(scope, href) || `https://www.linkedin.com/jobs/view/${id}/`,
      linkedin_url: `https://www.linkedin.com/jobs/view/${id}/`,
      posted,
      employment_type: employment,
      workplace_type: workplace,
      remote: REMOTE.test(lc(workplace))
    };
  }

  const api = { extract, decodeApplyUrl, jobIdFromUrl, findShowMore };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.IJExtract = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
