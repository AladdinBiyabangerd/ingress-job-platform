"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CATEGORY_ORDER, categoryLabel, languageLabel, text } from "../lib/copy";
import { jobsListParams } from "../lib/jobs-params";
import { lockBodyScroll, trapTab } from "../lib/focus-trap";
import { fetchMe } from "../lib/me-client";
import { recommendationsEnabled } from "../lib/product-features";
import { useMediaQuery } from "../lib/use-media-query";
import { FeaturedJob } from "./featured-job";
import { JobRow } from "./job-row";
import { MatchAside } from "./match-aside";
import { useInitialMe } from "./me-seed";
import { Shell } from "./shell";
import { TrendAside } from "./trend-aside";

const PAGE_SIZE = 20;
const TEXT_DEBOUNCE_MS = 300;
const EMPTY_FACETS = { languages: [], categories: [], stacks: [] };
const QUICK_CATEGORY_LIMIT = 4;

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

function matchToJob(match, listItem) {
  if (!match) return null;
  const id = Number(match.job_id);
  if (!Number.isFinite(id) || id <= 0) return null;
  const base = listItem && Number(listItem.id) === id ? listItem : {};
  return {
    id,
    title: match.title || base.title || "",
    company: match.company || base.company || "",
    company_slug: base.company_slug || "",
    city: match.city || base.city || "",
    remote: Boolean(match.remote ?? base.remote),
    relocation: Boolean(match.relocation ?? base.relocation),
    tech_stack: Array.isArray(base.tech_stack) ? base.tech_stack : [],
    category: match.category || base.category || "",
    language: match.language || base.language || "",
    salary: match.salary || base.salary || "",
    job_type: base.job_type || "",
    source_name: base.source_name || "",
    created_at: match.created_at || base.created_at || "",
    onsite: base.onsite,
    applications: base.applications,
    has_original: base.has_original,
  };
}

export function Home({
  locale,
  jobs = [],
  total = 0,
  pages = 1,
  facets = EMPTY_FACETS,
  error = false,
}) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [q, setQ] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("q") || "";
  });
  const [company, setCompany] = useState("");
  const [languages, setLanguages] = useState([]);
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
  const [items, setItems] = useState(jobs);
  const [resultTotal, setResultTotal] = useState(total);
  const [resultPages, setResultPages] = useState(Math.max(1, pages));
  const [facetData, setFacetData] = useState(facets?.languages ? facets : EMPTY_FACETS);
  const [loadError, setLoadError] = useState(Boolean(error));
  const [loading, setLoading] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [matches, setMatches] = useState([]);
  const compact = useMediaQuery("(max-width: 767px)");
  const panelRef = useRef(null);
  const toggleRef = useRef(null);
  const closeRef = useRef(null);
  const resultsRef = useRef(null);
  const skipFirstFetch = useRef(true);
  const prevTextKey = useRef(`${q}|${company}|${salaryMin}|${salaryMax}`);
  const prevFilterKey = useRef("");

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [initialMe]);

  useEffect(() => {
    if (!me?.authenticated || !recommendationsEnabled()) {
      setMatches([]);
      return undefined;
    }
    const controller = new AbortController();
    const lang = encodeURIComponent(locale || "az");
    fetch(`/api/auth/me/matches?lang=${lang}&limit=10`, {
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
    })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) return;
        setMatches(Array.isArray(data.matches) ? data.matches : []);
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        setMatches([]);
      });
    return () => controller.abort();
  }, [me?.authenticated, locale]);

  const filterKey = useMemo(
    () =>
      JSON.stringify({
        q,
        company,
        languages,
        remote,
        relocation,
        stacks,
        categories,
        when,
        sort,
        salaryMin,
        salaryMax,
      }),
    [q, company, languages, remote, relocation, stacks, categories, when, sort, salaryMin, salaryMax],
  );

  const languageOptions = useMemo(
    () => (Array.isArray(facetData.languages) ? facetData.languages : []).map((item) => item.code).filter(Boolean),
    [facetData],
  );
  const categoryOptions = useMemo(() => {
    const list = Array.isArray(facetData.categories) ? facetData.categories : [];
    const rank = (name) => {
      const index = CATEGORY_ORDER.indexOf(name);
      return index < 0 ? 99 : index;
    };
    return [...list].sort((a, b) => rank(a.name) - rank(b.name));
  }, [facetData]);
  const quickCategories = useMemo(() => {
    const list = Array.isArray(facetData.categories) ? [...facetData.categories] : [];
    list.sort((a, b) => (Number(b.total) || 0) - (Number(a.total) || 0));
    return list.slice(0, QUICK_CATEGORY_LIMIT);
  }, [facetData]);
  const techOptions = useMemo(() => {
    const list = Array.isArray(facetData.stacks) ? facetData.stacks : [];
    const query = techQuery.trim().toLowerCase();
    return list.filter((item) => !query || String(item.name || "").toLowerCase().includes(query));
  }, [facetData, techQuery]);

  const matchById = useMemo(() => {
    const map = new Map();
    for (const row of matches) {
      const id = Number(row.job_id);
      if (Number.isFinite(id) && typeof row.score === "number") map.set(id, row);
    }
    return map;
  }, [matches]);

  const featured = useMemo(() => {
    if (me?.authenticated && matches.length) {
      const top = matches[0];
      const listHit = items.find((job) => Number(job.id) === Number(top.job_id));
      const job = matchToJob(top, listHit);
      if (job?.title) {
        return { job, score: typeof top.score === "number" ? top.score : null };
      }
    }
    if (items[0]) return { job: items[0], score: matchById.get(Number(items[0].id))?.score ?? null };
    return null;
  }, [me?.authenticated, matches, items, matchById]);

  function toggle(list, setList, value) {
    setList(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  useEffect(() => {
    if (skipFirstFetch.current) {
      skipFirstFetch.current = false;
      prevFilterKey.current = filterKey;
      prevTextKey.current = `${q}|${company}|${salaryMin}|${salaryMax}`;
      if (!error && jobs.length > 0 && !q) return undefined;
    }
    if (prevFilterKey.current !== filterKey) {
      prevFilterKey.current = filterKey;
      if (page !== 1) {
        setPage(1);
        return undefined;
      }
    }
    const textKey = `${q}|${company}|${salaryMin}|${salaryMax}`;
    const debounceMs = textKey !== prevTextKey.current ? TEXT_DEBOUNCE_MS : 0;
    prevTextKey.current = textKey;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const params = jobsListParams({
        page,
        perPage: PAGE_SIZE,
        q,
        company,
        remote,
        relocation,
        when,
        sort,
        languages,
        categories,
        stacks,
        salaryMin,
        salaryMax,
      });
      setLoading(true);
      fetch(`/api/jobs?${params.toString()}`, {
        cache: "no-store",
        signal: controller.signal,
      })
        .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
          if (!ok) throw new Error("jobs");
          setItems(Array.isArray(data.items) ? data.items : []);
          setResultTotal(Number(data.total) || 0);
          setResultPages(Math.max(1, Number(data.pages) || 1));
          if (data.facets && typeof data.facets === "object") setFacetData(data.facets);
          setLoadError(false);
        })
        .catch((err) => {
          if (err?.name === "AbortError") return;
          setLoadError(true);
        })
        .finally(() => setLoading(false));
    }, debounceMs);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    page,
    error,
    jobs.length,
    filterKey,
    q,
    company,
    languages,
    remote,
    relocation,
    stacks,
    categories,
    when,
    sort,
    salaryMin,
    salaryMax,
  ]);

  function clear() {
    setQ("");
    setCompany("");
    setLanguages([]);
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
    if (typeof window !== "undefined" && window.location.search.includes("q=")) {
      const url = new URL(window.location.href);
      url.searchParams.delete("q");
      window.history.replaceState({}, "", url.pathname + url.search);
    }
  }

  const activeFilters =
    languages.length +
    categories.length +
    stacks.length +
    (remote ? 1 : 0) +
    (relocation ? 1 : 0) +
    (q.trim() ? 1 : 0) +
    (company.trim() ? 1 : 0) +
    (when !== "any" ? 1 : 0) +
    (salaryMin.trim() || salaryMax.trim() ? 1 : 0);

  const currentPage = Math.min(page, resultPages);

  useEffect(() => {
    if (!filtersOpen) return undefined;
    const toggleBtn = toggleRef.current;
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
      toggleBtn?.focus({ preventScroll: true });
    };
  }, [filtersOpen]);

  function applyFilters() {
    setFiltersOpen(false);
    const top = resultsRef.current?.getBoundingClientRect().top;
    if (typeof top === "number" && top < 0) {
      window.scrollTo({ top: window.scrollY + top - 12, behavior: "smooth" });
    }
  }

  function goToPage(next) {
    const clamped = Math.max(1, Math.min(resultPages, next));
    setPage(clamped);
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  const topMatch = matches[0];
  const authenticated = Boolean(me?.authenticated);

  return (
    <Shell locale={locale} mode="browse">
      <div className="home home-h2">
        {loadError ? <p className="note">{t.loadError}</p> : null}
        <div className="home-h2-layout">
          {featured?.job ? (
            <FeaturedJob locale={locale} job={featured.job} matchScore={featured.score} />
          ) : null}

          <aside className="home-h2-side">
            <TrendAside locale={locale} />
            {recommendationsEnabled() ? (
              <MatchAside
                locale={locale}
                authenticated={authenticated}
                topScore={typeof topMatch?.score === "number" ? topMatch.score : null}
                jobTitle={topMatch?.title || ""}
              />
            ) : null}
          </aside>

          <section className="open-roles" ref={resultsRef} aria-labelledby="open-roles-title">
            <div className="open-roles-head">
              <h2 id="open-roles-title">{t.openRoles}</h2>
              <p className="open-roles-count">{t.count(resultTotal)}</p>
            </div>

            <div className="filter-chips" role="toolbar" aria-label={t.filters}>
              <div className="filter-chips-scroll">
                <button
                  type="button"
                  className={categories.length === 0 ? "filter-chip is-on" : "filter-chip"}
                  onClick={() => setCategories([])}
                >
                  {t.allRoles}
                </button>
                {quickCategories.map(({ name }) => (
                  <button
                    key={name}
                    type="button"
                    className={categories.includes(name) ? "filter-chip is-on" : "filter-chip"}
                    onClick={() => toggle(categories, setCategories, name)}
                  >
                    {categoryLabel(locale, name)}
                  </button>
                ))}
                <button
                  type="button"
                  className={remote ? "filter-chip is-on" : "filter-chip"}
                  onClick={() => setRemote((value) => !value)}
                >
                  {t.remoteFilter}
                </button>
                <button
                  type="button"
                  className={relocation ? "filter-chip is-on" : "filter-chip"}
                  onClick={() => setRelocation((value) => !value)}
                >
                  {t.relocationFilter}
                </button>
                <label className="filter-chip filter-chip-select">
                  <span className="visually-hidden">{t.when}</span>
                  <select value={when} onChange={(event) => setWhen(event.target.value)}>
                    <option value="any">{t.anyTime}</option>
                    <option value="today">{t.today}</option>
                    <option value="week">{t.week}</option>
                  </select>
                </label>
              </div>
              <button
                ref={toggleRef}
                type="button"
                className="filter-chip filter-chip-more"
                aria-haspopup="dialog"
                aria-expanded={filtersOpen}
                aria-controls="job-filters"
                onClick={() => setFiltersOpen(true)}
              >
                <FilterIcon name="filter" />
                {t.filters}
                {activeFilters ? (
                  <>
                    <span className="filters-badge" aria-hidden="true">
                      {activeFilters}
                    </span>
                    <span className="visually-hidden">{`, ${t.filtersActive(activeFilters)}`}</span>
                  </>
                ) : null}
              </button>
            </div>

            {resultTotal === 0 && !loadError ? <p className="job-empty">{t.empty}</p> : null}

            <div className="job-row-list" data-compact={compact ? "true" : undefined}>
              {!compact && items.length ? (
                <div className="job-row-head" aria-hidden="true">
                  <span className="job-row-save" />
                  <span className="job-row-role">{t.jobRowRole}</span>
                  <span className="job-row-company">{t.companies}</span>
                  <span className="job-row-place">{t.factLocation}</span>
                  <span className="job-row-salary">{t.salaryFilter}</span>
                  <span className="job-row-posted">{t.factPosted}</span>
                  <span className="job-row-match">{t.jobRowMatch}</span>
                  <span className="job-row-open" />
                </div>
              ) : null}
              {items.map((job, index) => (
                <JobRow
                  key={job.id}
                  locale={locale}
                  job={job}
                  matchScore={matchById.get(Number(job.id))?.score ?? null}
                  active={index === 0}
                />
              ))}
            </div>

            {resultTotal > PAGE_SIZE ? (
              <nav className="pager" aria-label={t.pageOf(currentPage, resultPages)}>
                <button
                  type="button"
                  className="pager-btn"
                  disabled={currentPage <= 1 || loading}
                  onClick={() => goToPage(currentPage - 1)}
                >
                  {t.pagePrev}
                </button>
                <span className="pager-status">{t.pageOf(currentPage, resultPages)}</span>
                <button
                  type="button"
                  className="pager-btn"
                  disabled={currentPage >= resultPages || loading}
                  onClick={() => goToPage(currentPage + 1)}
                >
                  {t.pageNext}
                </button>
              </nav>
            ) : null}
          </section>
        </div>

        {filtersOpen ? (
          <>
            <div className="filter-backdrop" aria-hidden="true" onClick={() => setFiltersOpen(false)} />
            <aside
              ref={panelRef}
              id="job-filters"
              className="filter-panel is-open h2-filter-drawer"
              role="dialog"
              aria-modal="true"
              aria-labelledby="job-filters-title"
            >
              <div className="filter-head">
                <h2 id="job-filters-title">{t.filters}</h2>
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
              <fieldset className="filter-group">
                <legend className="filter-label">
                  <FilterIcon name="language" />
                  {t.language}
                </legend>
                <div className="checks scroll-set">
                  {languageOptions.map((code) => (
                    <label key={code} className="check">
                      <input
                        type="checkbox"
                        checked={languages.includes(code)}
                        onChange={() => toggle(languages, setLanguages, code)}
                      />
                      <span>{languageLabel(locale, code)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <div className="filter-group">
                <label className="stack">
                  <GroupLabel icon="company">{t.companies}</GroupLabel>
                  <input
                    type="search"
                    value={company}
                    placeholder={t.companyPlaceholder}
                    onChange={(event) => setCompany(event.target.value)}
                  />
                </label>
              </div>
              <label className="check">
                <input type="checkbox" checked={remote} onChange={(event) => setRemote(event.target.checked)} />
                <GroupLabel icon="remote">{t.remoteFilter}</GroupLabel>
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={relocation}
                  onChange={(event) => setRelocation(event.target.checked)}
                />
                <GroupLabel icon="relocation">{t.relocationFilter}</GroupLabel>
              </label>
              {categoryOptions.length ? (
                <fieldset className="filter-group">
                  <legend className="filter-label">
                    <FilterIcon name="category" />
                    {t.categoryFilter}
                  </legend>
                  <div className="checks scroll-set">
                    {categoryOptions.map(({ name, total: count }) => (
                      <label key={name} className="check">
                        <input
                          type="checkbox"
                          checked={categories.includes(name)}
                          onChange={() => toggle(categories, setCategories, name)}
                        />
                        <span>
                          {categoryLabel(locale, name)} <span className="check-count">{count}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              ) : null}
              <div className="filter-group">
                <label className="stack">
                  <GroupLabel icon="stack">{t.techStack}</GroupLabel>
                  <input
                    type="search"
                    value={techQuery}
                    placeholder={t.techPlaceholder}
                    onChange={(event) => setTechQuery(event.target.value)}
                  />
                </label>
                {techOptions.length ? (
                  <div className="checks scroll-set">
                    {techOptions.map(({ name, total: count }) => (
                      <label key={name} className="check">
                        <input
                          type="checkbox"
                          checked={stacks.includes(name)}
                          onChange={() => toggle(stacks, setStacks, name)}
                        />
                        <span>
                          {name} <span className="check-count">{count}</span>
                        </span>
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
              <div className="filter-actions">
                <button type="button" className="btn" onClick={clear}>
                  {t.filtersClear}
                </button>
                <button type="button" className="btn primary" onClick={applyFilters}>
                  {t.filtersApply}{" "}
                  <span className="filter-actions-count">({t.count(resultTotal)})</span>
                </button>
              </div>
            </aside>
          </>
        ) : null}
      </div>
    </Shell>
  );
}
