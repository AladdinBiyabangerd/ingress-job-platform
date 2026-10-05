"use client";

import { useEffect, useMemo, useState } from "react";
import { hrefFor, languageLabel, text } from "../lib/copy";
import { Shell } from "./shell";

const PAGE_SIZE = 20;
const REMOTE = /remote|uzaqdan|удал[её]н/i;
const AZ = /[əğıöüşçƏĞİÖÜŞÇ]/;
const RU = /[а-яёА-ЯЁ]/;

function unique(jobs, key) {
  const names = new Set();
  for (const job of jobs) {
    const value = (job[key] || "").trim();
    if (value) names.add(value);
  }
  return Array.from(names).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

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

const MONTHS = {
  az: ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avq", "sen", "okt", "noy", "dek"],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  ru: ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
};

function postedOn(value, locale) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
  const time = Date.parse(normalized);
  if (Number.isNaN(time)) return "";
  const date = new Date(time);
  const months = MONTHS[locale] || MONTHS.az;
  return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()}`;
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
  if (name === "source") {
    return (
      <svg {...props}>
        <path d="M4 2.75h8.5v10.5L8.25 11 4 13.25V2.75z" />
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
  const [cities, setCities] = useState([]);
  const [sources, setSources] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [inDescription, setInDescription] = useState(true);
  const [withCity, setWithCity] = useState(false);
  const [remote, setRemote] = useState(false);
  const [relocation, setRelocation] = useState(false);
  const [stacks, setStacks] = useState([]);
  const [techQuery, setTechQuery] = useState("");
  const [when, setWhen] = useState("any");
  const [sort, setSort] = useState("newest");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [page, setPage] = useState(1);

  const languageOptions = useMemo(() => {
    const order = ["az", "en", "ru", "tr", "es", "uk", "de", "fr", "pt"];
    const codes = new Set(jobs.map((job) => languageOf(job)).filter(Boolean));
    return Array.from(codes).sort((a, b) => {
      const ai = order.indexOf(a);
      const bi = order.indexOf(b);
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi) || (a < b ? -1 : a > b ? 1 : 0);
    });
  }, [jobs]);
  const cityOptions = useMemo(() => unique(jobs, "city"), [jobs, t.lang]);
  const sourceOptions = useMemo(() => unique(jobs, "source_name"), [jobs, t.lang]);
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
  const companyOptions = useMemo(() => {
    const q = company.trim().toLowerCase();
    return unique(jobs, "company").filter((name) => !q || name.toLowerCase().includes(q));
  }, [jobs, company]);

  function toggle(list, setList, value) {
    setList(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const companyQuery = company.trim().toLowerCase();
    const filtered = jobs.filter((job) => {
      if (cities.length && !cities.includes(job.city)) return false;
      if (sources.length && !sources.includes(job.source_name)) return false;
      if (companies.length && !companies.includes(job.company)) return false;
      if (languages.length && !languages.includes(languageOf(job))) return false;
      if (withCity && !job.city) return false;
      if (remote) {
        const looksRemote = job.remote || !job.city || REMOTE.test(`${job.title} ${job.text}`);
        if (!looksRemote) return false;
      }
      if (relocation && !job.relocation) return false;
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
  }, [jobs, query, company, cities, sources, companies, languages, inDescription, withCity, remote, relocation, stacks, when, sort, salaryMin, salaryMax, t.lang]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return visible.slice(start, start + PAGE_SIZE);
  }, [visible, currentPage]);

  useEffect(() => {
    setPage(1);
  }, [query, company, cities, sources, companies, languages, inDescription, withCity, remote, relocation, stacks, when, sort, salaryMin, salaryMax]);

  function clear() {
    setQuery("");
    setCompany("");
    setCities([]);
    setSources([]);
    setCompanies([]);
    setLanguages([]);
    setInDescription(true);
    setWithCity(false);
    setRemote(false);
    setRelocation(false);
    setStacks([]);
    setTechQuery("");
    setWhen("any");
    setSort("newest");
    setSalaryMin("");
    setSalaryMax("");
    setPage(1);
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
      <section className="hero">
        <div className="hero-top">
          <div>
            <p className="eco-kicker">{t.ecosystemLine}</p>
            <h1>{t.heading}</h1>
            <p className="lede">{t.lede}</p>
          </div>
          <p className="hero-count">{t.count(jobs.length)}</p>
        </div>
        <form className="hero-search" role="search" onSubmit={(event) => event.preventDefault()}>
          <label className="hero-search-label" htmlFor="job-search">{t.search}</label>
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
      </section>
      {error ? <p className="note">{t.loadError}</p> : null}
      <div className="board">
        <section className="results">
          <p className="count">{t.count(visible.length)}</p>
          {visible.length === 0 && !error ? <p className="job-empty">{t.empty}</p> : null}
          <div className="job-list">
            {pageItems.map((job) => {
              const when = postedOn(job.created_at, locale);
              const place = job.remote ? t.placeRemote : (job.city || t.noCity);
              const stack = stackOf(job);
              return (
                <a key={job.id} className="job-card" href={hrefFor(locale, { jobId: job.id })}>
                  <span className="job-card-body">
                    <span className="job-kicker">
                      <span className="job-company">{job.company || t.noCompany}</span>
                      {job.source_name ? <span className="source-pill">{job.source_name}</span> : null}
                    </span>
                    <h2>{job.title}</h2>
                    {stack.length ? (
                      <span className="tech-chips" aria-label={t.techStack}>
                        {stack.slice(0, 6).map((name) => (
                          <span key={name} className="tech-chip">{name}</span>
                        ))}
                        {stack.length > 6 ? <span className="tech-chip more">+{stack.length - 6}</span> : null}
                      </span>
                    ) : null}
                    <span className="job-facts">
                      <span className="job-fact">
                        <FilterIcon name="city" />
                        {place}
                      </span>
                      {job.relocation ? (
                        <span className="job-fact">
                          <FilterIcon name="relocation" />
                          {t.relocationBadge}
                        </span>
                      ) : null}
                      {when ? (
                        <span className="job-fact">
                          <FilterIcon name="date" />
                          <time dateTime={job.created_at}>{when}</time>
                        </span>
                      ) : null}
                    </span>
                  </span>
                  <span className="job-open">{t.openRole}</span>
                </a>
              );
            })}
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
        <aside className="filter-panel">
          <div className="filter-head">
            <h2>{t.filters}</h2>
            <button type="button" className="text-btn" onClick={clear}>{t.clear}</button>
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
            {companyOptions.length ? (
              <div className="checks scroll-set">
                {companyOptions.map((name) => (
                  <label key={name} className="check">
                    <input type="checkbox" checked={companies.includes(name)} onChange={() => toggle(companies, setCompanies, name)} />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
            ) : null}
          </div>
          <label className="check">
            <input type="checkbox" checked={withCity} onChange={(event) => setWithCity(event.target.checked)} />
            <GroupLabel icon="with-city">{t.withCity}</GroupLabel>
          </label>
          <label className="check">
            <input type="checkbox" checked={remote} onChange={(event) => setRemote(event.target.checked)} />
            <GroupLabel icon="remote">{t.remote}</GroupLabel>
          </label>
          <label className="check">
            <input type="checkbox" checked={relocation} onChange={(event) => setRelocation(event.target.checked)} />
            <GroupLabel icon="relocation">{t.relocationFilter}</GroupLabel>
          </label>
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
          {sourceOptions.length ? (
            <fieldset className="filter-group">
              <legend className="filter-label">
                <FilterIcon name="source" />
                {t.sources}
              </legend>
              <div className="checks scroll-set">
                {sourceOptions.map((name) => (
                  <label key={name} className="check">
                    <input type="checkbox" checked={sources.includes(name)} onChange={() => toggle(sources, setSources, name)} />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ) : null}
          {cityOptions.length ? (
            <fieldset className="filter-group">
              <legend className="filter-label">
                <FilterIcon name="city" />
                {t.city}
              </legend>
              <div className="checks scroll-set">
                {cityOptions.map((name) => (
                  <label key={name} className="check">
                    <input type="checkbox" checked={cities.includes(name)} onChange={() => toggle(cities, setCities, name)} />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          ) : null}
        </aside>
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
