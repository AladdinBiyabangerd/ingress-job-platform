"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CATEGORY_ORDER, categoryLabel, languageLabel, text } from "../lib/copy";
import { lockBodyScroll, trapTab } from "../lib/focus-trap";
import { useMediaQuery } from "../lib/use-media-query";
import { JobCard } from "./job-card";
import { Shell } from "./shell";
import { PageHeader } from "./page-header";

const PAGE_SIZE = 20;
const AZ = /[əğıöüşçƏĞİÖÜŞÇ]/;
const RU = /[а-яёА-ЯЁ]/;

function stackOf(job) {
  return Array.isArray(job.tech_stack) ? job.tech_stack : [];
}

function languageOf(job) {
  if (job.language) return job.language;
  const sample = `${job.title}\n${job.text}`;
  if (AZ.test(sample)) return "az";
  if (RU.test(sample)) return "ru";
  return "en";
}

function ageDays(job) {
  const time = Date.parse(job.created_at || "");
  if (Number.isNaN(time)) return null;
  return (Date.now() - time) / 86400000;
}

/** First number in free-text salary; currency words/symbols ignored. null if none. */
function parseSalaryAmount(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const cleaned = raw
    .replace(/[₼$€£¥₽]/g, " ")
    .replace(/\b(azn|usd|eur|gbp|try|rub|rur|manat|dollar|dollars|euro|euros|руб(?:ль|ля|лей)?|доллар(?:а|ов|ы)?|евро|манат)\b/gi, " ");
  const match = cleaned.match(/\d{1,3}(?:[.,\s]\d{3})+|\d+/);
  if (!match) return null;
  const token = match[0];
  const digits = /^\d{1,3}([.,\s]\d{3})+$/.test(token)
    ? token.replace(/[.,\s]/g, "")
    : token.match(/\d+/)[0];
  const num = Number(digits);
  return Number.isFinite(num) ? num : null;
}

function normalizeSalaryText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/ё/g, "е")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ə/g, "e")
    .replace(/ı/g, "i")
    .replace(/\s+/g, " ")
    .trim();
}

function isNegotiableSalary(value) {
  const normalized = normalizeSalaryText(value);
  return [
    /\bmuqavile\s+ile\b/u,
    /\brazilasma\b/u,
    /\bnegotiable\b/u,
    /\bby[\s-]+agreement\b/u,
    /(?:^|[^\p{L}])договорная(?:$|[^\p{L}])/u,
    /(?:^|[^\p{L}])по\s+договоренности(?:$|[^\p{L}])/u,
  ].some((pattern) => pattern.test(normalized));
}

function FilterIcon({ name }) {
  const props = {
    className: "filter-icon",
    width: 16,
    height: 16,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
    focusable: "false",
  };
  if (name === "filter") {
    return (
      <svg {...props}>
        <path d="M2.5 4.5h7M12.5 4.5h1M2.5 11.5h1M6.5 11.5h7" />
        <circle cx="11" cy="4.5" r="1.5" />
        <circle cx="5" cy="11.5" r="1.5" />
      </svg>
    );
  }
  if (name === "sort") {
    return (
      <svg {...props}>
        <path d="M3 4h10M5 8h6M7 12h2" />
      </svg>
    );
  }
  if (name === "date") {
    return (
      <svg {...props}>
        <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
        <path d="M2.5 6.5h11M5.5 2v2M10.5 2v2" />
      </svg>
    );
  }
  if (name === "search") {
    return (
      <svg {...props}>
        <circle cx="7" cy="7" r="3.25" />
        <path d="M9.6 9.6 13 13" />
      </svg>
    );
  }
  if (name === "language") {
    return (
      <svg {...props}>
        <circle cx="8" cy="8" r="5.25" />
        <path d="M2.75 8h10.5M8 2.75c1.5 1.7 2.25 3.4 2.25 5.25S9.5 11.55 8 13.25C6.5 11.55 5.75 9.85 5.75 8S6.5 4.45 8 2.75z" />
      </svg>
    );
  }
  if (name === "company") {
    return (
      <svg {...props}>
        <path d="M3 13.5V3.5h5.5V13.5M8.5 6.5H13v7M5 6h1.5M5 8.5h1.5M10 9h1.5M10 11h1.5" />
      </svg>
    );
  }
  if (name === "city") {
    return (
      <svg {...props}>
        <path d="M8 13.5s4.25-3.7 4.25-6.55a4.25 4.25 0 0 0-8.5 0C3.75 9.8 8 13.5 8 13.5z" />
        <circle cx="8" cy="6.9" r="1.35" />
      </svg>
    );
  }
  if (name === "salary") {
    return (
      <svg {...props}>
        <rect x="2.5" y="4" width="11" height="8" rx="1.5" />
        <path d="M8 6.25v3.5M6.5 7.25c.4-.55 1-.85 1.5-.85s1.1.3 1.5.85M6.5 9.75c.4.55 1 .85 1.5.85s1.1-.3 1.5-.85" />
      </svg>
    );
  }
  if (name === "relocation") {
    return (
      <svg {...props}>
        <path d="M2.5 9.5 13.5 4l-2 9-3-3.25L6 11.5V8.5" />
        <path d="M8.5 9.75 13.5 4" />
      </svg>
    );
  }
  if (name === "category") {
    return (
      <svg {...props}>
        <rect x="2.5" y="2.5" width="4.5" height="4.5" rx="1" />
        <rect x="9" y="2.5" width="4.5" height="4.5" rx="1" />
        <rect x="2.5" y="9" width="4.5" height="4.5" rx="1" />
        <rect x="9" y="9" width="4.5" height="4.5" rx="1" />
      </svg>
    );
  }
  if (name === "stack") {
    return (
      <svg {...props}>
        <path d="M6 4.5 2.75 8 6 11.5M10 4.5 13.25 8 10 11.5" />
      </svg>
    );
  }
  if (name === "remote") {
    return (
      <svg {...props}>
        <rect x="2.25" y="3.25" width="11.5" height="7.5" rx="1.25" />
        <path d="M6 13h4M8 10.75V13" />
      </svg>
    );
  }
  return (
    <svg {...props}>
      <path d="M8 13.5s3.75-3.3 3.75-5.8a3.75 3.75 0 0 0-7.5 0C4.25 10.2 8 13.5 8 13.5z" />
      <path d="M6.4 7.6 7.5 8.7 9.7 6.5" />
    </svg>
  );
}

function GroupLabel({ icon, children }) {
  return (
    <span className="filter-label">
      <FilterIcon name={icon} />
      {children}
    </span>
  );
}

export function Home({ locale, jobs, error }) {
  const t = text(locale);
  const [query, setQuery] = useState("");
  const [company, setCompany] = useState("");
  const [languages, setLanguages] = useState([]);
  const [inDescription, setInDescription] = useState(true);
  const [remote, setRemote] = useState(false);
  const [relocation, setRelocation] = useState(false);
  const [stacks, setStacks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [techQuery, setTechQuery] = useState("");
  const [when, setWhen] = useState("any");
  const [sort, setSort] = useState("newest");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const compact = useMediaQuery("(max-width: 900px)");
  const drawerOpen = compact && filtersOpen;
  const panelRef = useRef(null);
  const toggleRef = useRef(null);
  const closeRef = useRef(null);
  const resultsRef = useRef(null);

  const languageOptions = useMemo(() => {
    const order = ["az", "en", "ru", "tr", "es", "uk", "de", "fr", "pt"];
    const codes = new Set(jobs.map((job) => languageOf(job)).filter(Boolean));
    return Array.from(codes).sort((a, b) => {
      const ai = order.indexOf(a);
      const bi = order.indexOf(b);
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi) || (a < b ? -1 : a > b ? 1 : 0);
    });
  }, [jobs]);
  const techOptions = useMemo(() => {
    const counts = new Map();
    for (const job of jobs) {
      for (const name of stackOf(job)) counts.set(name, (counts.get(name) || 0) + 1);
    }
    const q = techQuery.trim().toLowerCase();
    return Array.from(counts.entries())
      .filter(([name]) => !q || name.toLowerCase().includes(q))
      .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
      .map(([name, total]) => ({ name, total }));
  }, [jobs, techQuery]);
  const categoryOptions = useMemo(() => {
    const counts = new Map();
    for (const job of jobs) {
      if (job.category) counts.set(job.category, (counts.get(job.category) || 0) + 1);
    }
    const rank = (name) => {
      const index = CATEGORY_ORDER.indexOf(name);
      return index < 0 ? 99 : index;
    };
    return Array.from(counts.entries())
      .sort((a, b) => rank(a[0]) - rank(b[0]))
      .map(([name, total]) => ({ name, total }));
  }, [jobs]);
  function toggle(list, setList, value) {
    setList(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const companyQuery = company.trim().toLowerCase();
    const filtered = jobs.filter((job) => {
      if (languages.length && !languages.includes(languageOf(job))) return false;
      if (remote && !(job.remote || job.job_type === "uzaqdan")) return false;
      if (relocation && !job.relocation) return false;
      if (categories.length && !categories.includes(job.category)) return false;
      if (stacks.length) {
        const own = stackOf(job);
        if (!stacks.some((name) => own.includes(name))) return false;
      }
      const days = ageDays(job);
      if (when === "today" && (days === null || days >= 1)) return false;
      if (when === "week" && (days === null || days >= 7)) return false;
      const minRaw = salaryMin.trim();
      const maxRaw = salaryMax.trim();
      const minBound = minRaw === "" ? null : Number(minRaw);
      const maxBound = maxRaw === "" ? null : Number(maxRaw);
      const hasMin = minBound !== null && Number.isFinite(minBound);
      const hasMax = maxBound !== null && Number.isFinite(maxBound);
      if (hasMin || hasMax) {
        const amount = parseSalaryAmount(job.salary);
        if (amount === null && !isNegotiableSalary(job.salary)) return false;
        if (amount !== null) {
          if (hasMin && amount < minBound) return false;
          if (hasMax && amount > maxBound) return false;
        }
      }
      if (companyQuery && !(job.company || "").toLowerCase().includes(companyQuery)) return false;
      if (!q) return true;
      const haystack = inDescription
        ? `${job.title} ${job.company} ${job.text}`
        : `${job.title} ${job.company}`;
      return haystack.toLowerCase().includes(q);
    });
    const sorted = [...filtered];
    sorted.sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title, t.lang);
      const at = Date.parse(a.created_at || "") || 0;
      const bt = Date.parse(b.created_at || "") || 0;
      return sort === "oldest" ? at - bt : bt - at;
    });
    return sorted;
  }, [jobs, query, company, languages, inDescription, remote, relocation, stacks, categories, when, sort, salaryMin, salaryMax, t.lang]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return visible.slice(start, start + PAGE_SIZE);
  }, [visible, currentPage]);

  useEffect(() => {
    setPage(1);
  }, [query, company, languages, inDescription, remote, relocation, stacks, categories, when, sort, salaryMin, salaryMax]);

  function clear() {
    setQuery("");
    setCompany("");
    setLanguages([]);
    setInDescription(true);
    setRemote(false);
    setRelocation(false);
    setStacks([]);
    setCategories([]);
    setTechQuery("");
    setWhen("any");
    setSort("newest");
    setSalaryMin("");
    setSalaryMax("");
    setPage(1);
  }

  const activeFilters =
    languages.length +
    categories.length +
    stacks.length +
    (remote ? 1 : 0) +
    (relocation ? 1 : 0) +
    (company.trim() ? 1 : 0) +
    (when !== "any" ? 1 : 0) +
    (salaryMin.trim() || salaryMax.trim() ? 1 : 0);

  useEffect(() => {
    if (!compact) setFiltersOpen(false);
  }, [compact]);

  useEffect(() => {
    if (!drawerOpen) return undefined;
    const toggle = toggleRef.current;
    const unlock = lockBodyScroll();
    closeRef.current?.focus();
    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setFiltersOpen(false);
        return;
      }
      trapTab(event, panelRef.current);
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      unlock();
      toggle?.focus({ preventScroll: true });
    };
  }, [drawerOpen]);

  function applyFilters() {
    setFiltersOpen(false);
    const top = resultsRef.current?.getBoundingClientRect().top;
    if (typeof top === "number" && top < 0) {
      window.scrollTo({ top: window.scrollY + top - 12, behavior: "smooth" });
    }
  }

  function goToPage(next) {
    const clamped = Math.max(1, Math.min(totalPages, next));
    setPage(clamped);
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  return (
    <Shell locale={locale} mode="browse">
      <div className="home">
      <PageHeader title={t.heading} count={t.count(jobs.length)} lede={t.lede}>
        <form className="hero-search" role="search" onSubmit={(event) => event.preventDefault()}>
          <label className="visually-hidden" htmlFor="job-search">{t.search}</label>
          <div className="hero-search-bar">
            <FilterIcon name="search" />
            <input
              id="job-search"
              type="search"
              value={query}
              placeholder={t.searchPlaceholder}
              autoComplete="off"
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </form>
      </PageHeader>
      {error ? <p className="note">{t.loadError}</p> : null}
      <div className="board">
        <section className="results" ref={resultsRef}>
          <div className="results-bar">
            <p className="count">{t.count(visible.length)}</p>
            <button
              ref={toggleRef}
              type="button"
              className="filters-toggle"
              aria-haspopup="dialog"
              aria-expanded={drawerOpen}
              aria-controls="job-filters"
              onClick={() => setFiltersOpen(true)}
            >
              <FilterIcon name="filter" />
              {t.filters}
              {activeFilters ? (
                <>
                  <span className="filters-badge" aria-hidden="true">{activeFilters}</span>
                  <span className="visually-hidden">{`, ${t.filtersActive(activeFilters)}`}</span>
                </>
              ) : null}
            </button>
          </div>
          {visible.length === 0 && !error ? <p className="job-empty">{t.empty}</p> : null}
          <div className="job-list">
            {pageItems.map((job) => (
              <JobCard key={job.id} locale={locale} job={job} />
            ))}
          </div>
          {visible.length > PAGE_SIZE ? (
            <nav className="pager" aria-label={t.pageOf(currentPage, totalPages)}>
              <button
                type="button"
                className="pager-btn"
                disabled={currentPage <= 1}
                onClick={() => goToPage(currentPage - 1)}
              >
                {t.pagePrev}
              </button>
              <span className="pager-status">{t.pageOf(currentPage, totalPages)}</span>
              <button
                type="button"
                className="pager-btn"
                disabled={currentPage >= totalPages}
                onClick={() => goToPage(currentPage + 1)}
              >
                {t.pageNext}
              </button>
            </nav>
          ) : null}
        </section>
        <aside
          ref={panelRef}
          id="job-filters"
          className={drawerOpen ? "filter-panel is-open" : "filter-panel"}
          role={drawerOpen ? "dialog" : undefined}
          aria-modal={drawerOpen ? "true" : undefined}
          aria-labelledby="job-filters-title"
        >
          <div className="filter-head">
            <h2 id="job-filters-title">{t.filters}</h2>
            {drawerOpen ? (
              <button
                ref={closeRef}
                type="button"
                className="filter-close"
                aria-label={t.filtersClose}
                onClick={() => setFiltersOpen(false)}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            ) : (
              <button type="button" className="text-btn" onClick={clear}>{t.clear}</button>
            )}
          </div>
          <label className="stack">
            <GroupLabel icon="sort">{t.sort}</GroupLabel>
            <select value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="newest">{t.newest}</option>
              <option value="oldest">{t.oldest}</option>
              <option value="title">{t.byTitle}</option>
            </select>
          </label>
          <label className="stack">
            <GroupLabel icon="date">{t.when}</GroupLabel>
            <select value={when} onChange={(event) => setWhen(event.target.value)}>
              <option value="any">{t.anyTime}</option>
              <option value="today">{t.today}</option>
              <option value="week">{t.week}</option>
            </select>
          </label>
          <div className="filter-group">
            <GroupLabel icon="search">{t.search}</GroupLabel>
            <label className="check">
              <input type="checkbox" checked={inDescription} onChange={(event) => setInDescription(event.target.checked)} />
              <span>{t.inDescription}</span>
            </label>
          </div>
          <fieldset className="filter-group">
            <legend className="filter-label">
              <FilterIcon name="language" />
              {t.language}
            </legend>
            <div className="checks scroll-set">
              {languageOptions.map((code) => (
                <label key={code} className="check">
                  <input type="checkbox" checked={languages.includes(code)} onChange={() => toggle(languages, setLanguages, code)} />
                  <span>{languageLabel(locale, code)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="filter-group">
            <label className="stack">
              <GroupLabel icon="company">{t.companies}</GroupLabel>
              <input type="search" value={company} placeholder={t.companyPlaceholder} onChange={(event) => setCompany(event.target.value)} />
            </label>
          </div>
          <label className="check">
            <input type="checkbox" checked={remote} onChange={(event) => setRemote(event.target.checked)} />
            <GroupLabel icon="remote">{t.remoteFilter}</GroupLabel>
          </label>
          <label className="check">
            <input type="checkbox" checked={relocation} onChange={(event) => setRelocation(event.target.checked)} />
            <GroupLabel icon="relocation">{t.relocationFilter}</GroupLabel>
          </label>
          {categoryOptions.length ? (
            <fieldset className="filter-group">
              <legend className="filter-label">
                <FilterIcon name="category" />
                {t.categoryFilter}
              </legend>
              <div className="checks scroll-set">
                {categoryOptions.map(({ name, total }) => (
                  <label key={name} className="check">
                    <input type="checkbox" checked={categories.includes(name)} onChange={() => toggle(categories, setCategories, name)} />
                    <span>{categoryLabel(locale, name)} <span className="check-count">{total}</span></span>
                  </label>
                ))}
              </div>
            </fieldset>
          ) : null}
          <div className="filter-group">
            <label className="stack">
              <GroupLabel icon="stack">{t.techStack}</GroupLabel>
              <input type="search" value={techQuery} placeholder={t.techPlaceholder} onChange={(event) => setTechQuery(event.target.value)} />
            </label>
            {techOptions.length ? (
              <div className="checks scroll-set">
                {techOptions.map(({ name, total }) => (
                  <label key={name} className="check">
                    <input type="checkbox" checked={stacks.includes(name)} onChange={() => toggle(stacks, setStacks, name)} />
                    <span>{name} <span className="check-count">{total}</span></span>
                  </label>
                ))}
              </div>
            ) : null}
          </div>
          <div className="filter-group">
            <GroupLabel icon="salary">{t.salaryFilter}</GroupLabel>
            <div className="salary-bounds">
              <label>
                <span>{t.salaryMin}</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min="0"
                  step="1"
                  value={salaryMin}
                  placeholder={t.salaryMin}
                  onChange={(event) => setSalaryMin(event.target.value)}
                />
              </label>
              <label>
                <span>{t.salaryMax}</span>
                <input
                  type="number"
                  inputMode="numeric"
                  min="0"
                  step="1"
                  value={salaryMax}
                  placeholder={t.salaryMax}
                  onChange={(event) => setSalaryMax(event.target.value)}
                />
              </label>
            </div>
            <p className="salary-note">{t.salaryNote}</p>
          </div>
          {drawerOpen ? (
            <div className="filter-actions">
              <button type="button" className="btn" onClick={clear}>{t.filtersClear}</button>
              <button type="button" className="btn primary" onClick={applyFilters}>
                {t.filtersApply}{" "}
                <span className="filter-actions-count">({t.count(visible.length)})</span>
              </button>
            </div>
          ) : null}
        </aside>
        {drawerOpen ? <div className="filter-backdrop" aria-hidden="true" onClick={() => setFiltersOpen(false)} /> : null}
      </div>
      {t.faq?.items?.length ? (
        <section className="home-faq" id="faq" aria-labelledby="home-faq-title">
          <p className="home-faq-eyebrow">{t.faq.eyebrow}</p>
          <h2 id="home-faq-title">{t.faq.title}</h2>
          <div className="home-faq-list">
            {t.faq.items.map((item, index) => (
              <details key={item.q} open={index === 0}>
                <summary>{item.q}</summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </section>
      ) : null}
      </div>
    </Shell>
  );
}
