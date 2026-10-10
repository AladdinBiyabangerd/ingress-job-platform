// Passiv oxuyucu: yalnız ekranda artıq olan DOM-u oxuyur.
// Heç bir əlavə sorğu göndərmir, səhifələrə avtomatik keçmir, klikləmir.
(() => {
  let recording = false;
  let timer = null;
  const sent = new Map(); // id -> göndərilmiş imza

  const txt = (el) => (el ? (el.innerText || el.textContent || "").replace(/\s+\n/g, "\n").trim() : "");
  const first = (sels, root = document) => {
    for (const s of sels) {
      const el = root.querySelector(s);
      if (el && txt(el)) return el;
    }
    return null;
  };

  function currentId() {
    const m = location.pathname.match(/\/jobs\/view\/(?:[^/]*-)?(\d{5,})/);
    if (m) return m[1];
    const q = new URLSearchParams(location.search).get("currentJobId");
    if (q && /^\d{5,}$/.test(q)) return q;
    return "";
  }

  function jsonLd() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const d = JSON.parse(s.textContent);
        const arr = Array.isArray(d) ? d : [d];
        for (const x of arr) if (x && x["@type"] === "JobPosting") return x;
      } catch (_) {}
    }
    return null;
  }

  function decodeApply(href) {
    if (!href) return "";
    try {
      const u = new URL(href, location.href);
      if (/linkedin\.com$/.test(u.hostname) && /\/(safety\/go|redir\/redirect)/.test(u.pathname)) {
        const target = u.searchParams.get("url");
        return target && /^https?:/.test(target) ? target : "";
      }
      if (/(^|\.)linkedin\.com$/.test(u.hostname)) return "";
      return /^https?:/.test(u.protocol) ? u.href : "";
    } catch (_) {
      return "";
    }
  }

  function findApply(scope) {
    const nodes = scope.querySelectorAll("a[href], button");
    for (const n of nodes) {
      const label = (n.getAttribute("aria-label") || txt(n)).toLowerCase();
      if (!/\bapply\b/.test(label) || /easy apply/.test(label)) continue;
      const href = n.tagName === "A" ? n.getAttribute("href") : n.closest("a")?.getAttribute("href");
      const url = decodeApply(href);
      if (url) return url;
    }
    return "";
  }

  function extract() {
    const id = currentId();
    if (!id) return null;
    const ld = location.pathname.startsWith("/jobs/view/") ? jsonLd() : null;
    const pane =
      document.querySelector(".jobs-search__job-details--container, .job-details-jobs-unified-top-card__container--two-pane, .scaffold-layout__detail") ||
      document;
    const top = pane.querySelector("[class*='unified-top-card']")?.parentElement || pane;

    let title = txt(first(["[class*='job-title'] h1", "h1.t-24", "h1", "[class*='job-title']"], pane));
    let company = txt(first(["[class*='company-name'] a", "[class*='company-name']", "a[href*='/company/']"], pane));
    let location_ = txt(first(["[class*='primary-description'] .tvm__text", "[class*='primary-description-container'] span", "[class*='bullet']"], pane));
    let desc = txt(first(["#job-details", ".jobs-description__content", ".jobs-box__html-content", "[class*='jobs-description']"], pane));
    let posted = "";
    const meta = txt(first(["[class*='primary-description-container']"], pane));
    const pm = meta.match(/(\d+\s+(?:minute|hour|day|week|month)s?\s+ago|Reposted[^·\n]*|\d+\s+(?:dəqiqə|saat|gün|həftə|ay)\s+əvvəl)/i);
    if (pm) posted = pm[0].trim();
    let employment = "";
    const chips = [...pane.querySelectorAll("[class*='job-insight'], [class*='preferences'] button, [class*='workplace-type']")].map(txt).join(" | ");
    const em = chips.match(/\b(Full-time|Part-time|Contract|Temporary|Internship|Volunteer|Freelance)\b/i);
    if (em) employment = em[1];
    const remote = /\bremote\b/i.test(chips) || /\bremote\b/i.test(location_);

    if (ld) {
      title = title || ld.title || "";
      company = company || ld.hiringOrganization?.name || "";
      const a = ld.jobLocation?.address;
      location_ = location_ || [a?.addressLocality, a?.addressCountry?.name || a?.addressCountry].filter(Boolean).join(", ");
      if (!desc && ld.description) {
        const d = document.createElement("div");
        d.innerHTML = ld.description;
        desc = txt(d);
      }
      posted = posted || ld.datePosted || "";
      employment = employment || (Array.isArray(ld.employmentType) ? ld.employmentType[0] : ld.employmentType) || "";
    }
    if (!title) return null;
    const apply_url = findApply(top === document ? pane : pane);
    return {
      linkedin_id: id,
      title,
      company,
      location: location_.split("\n")[0].replace(/\s*·.*$/, "").trim(),
      description: desc,
      apply_url,
      linkedin_url: `https://www.linkedin.com/jobs/view/${id}/`,
      posted,
      employment_type: employment,
      remote
    };
  }

  function run() {
    if (!recording) return;
    const job = extract();
    if (!job || !job.description) return; // təsvir hələ yüklənməyib, sonraki dəyişikliyi gözlə
    const sig = [job.title, job.company, job.description.length, job.apply_url].join("|");
    if (sent.get(job.linkedin_id) === sig) return;
    sent.set(job.linkedin_id, sig);
    chrome.runtime.sendMessage({ type: "capture", job }).catch(() => {});
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(run, 1200);
  }

  new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", schedule);

  chrome.storage.local.get({ recording: false }).then((s) => {
    recording = !!s.recording;
    if (recording) schedule();
  });
  chrome.storage.onChanged.addListener((ch) => {
    if (ch.recording) {
      recording = !!ch.recording.newValue;
      if (recording) {
        sent.clear();
        schedule();
      }
    }
  });
})();
