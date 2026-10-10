"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CATEGORY_ORDER, categoryLabel, hrefFor, languageLabel, text } from "../lib/copy";
import { jobsListParams } from "../lib/jobs-params";
import { lockBodyScroll, trapTab } from "../lib/focus-trap";
import { useMediaQuery } from "../lib/use-media-query";
import { BoardAcademyPromo, BoardSideNav } from "./board-side-nav";
import { JobBoardCard } from "./job-board-card";
import { Shell } from "./shell";

const PAGE_SIZE = 20;
const TEXT_DEBOUNCE_MS = 300;
const EMPTY_FACETS = { languages: [], categories: [], stacks: [], cities: [], remote_total: 0 };
/** Matches `--dur-exit` in globals.css (~70% of `--dur-base`). */
const DRAWER_EXIT_MS = 154;
const DRAWER_EXIT_REDUCED_MS = 90;

function FilterIcon() {
  return (
    <svg
      className="filter-icon"
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M2.5 4.5h7M12.5 4.5h1M2.5 11.5h1M6.5 11.5h7" />
      <circle cx="11" cy="4.5" r="1.5" />
      <circle cx="5" cy="11.5" r="1.5" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </svg>
  );
}

function LocationIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 21s7-5.5 7-11a7 7 0 10-14 0c0 5.5 7 11 7 11z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

function LanguageIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" />
    </svg>
  );
}

function CategoryIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function ResetIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 12a9 9 0 109-9" />
      <path d="M3 4v5h5" />
    </svg>
  );
}

function FilterPanelBody({
  t,
  locale,
  cityOptions,
  remoteTotal,
  languageOptions,
  categoryOptions,
  techOptions,
  techQuery,
  setTechQuery,
  city,
  setCity,
  languages,
  setLanguages,
  remote,
  setRemote,
  relocation,
  setRelocation,
  categories,
  setCategories,
  stacks,
  setStacks,
  salaryMin,
  setSalaryMin,
  salaryMax,
  setSalaryMax,
  company,
  setCompany,
  when,
  setWhen,
  toggle,
  clear,
}) {
  return (
    <>
      <fieldset className="home-board-filter-group">
        <legend>{t.locationFilter}</legend>
        <div className="home-board-checks">
          {cityOptions.map(({ name, total: count }) => (
            <label key={name} className="home-board-check">
              <input
                type="checkbox"
                checked={city.toLowerCase() === String(name).toLowerCase()}
                onChange={() =>
                  setCity(city.toLowerCase() === String(name).toLowerCase() ? "" : name)
                }
              />
              <span className="home-board-check-label">{name}</span>
              <span className="home-board-check-count">{count}</span>
            </label>
          ))}
          <label className="home-board-check">
            <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} />
            <span className="home-board-check-label">{t.placeRemote}</span>
            {remoteTotal ? <span className="home-board-check-count">{remoteTotal}</span> : null}
          </label>
        </div>
      </fieldset>

      <fieldset className="home-board-filter-group">
        <legend>{t.language}</legend>
        <div className="home-board-checks">
          {languageOptions.map((code) => (
            <label key={code} className="home-board-check">
              <input
                type="checkbox"
                checked={languages.includes(code)}
                onChange={() => toggle(languages, setLanguages, code)}
              />
              <span className="home-board-check-label">{languageLabel(locale, code)}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="home-board-filter-group">
        <legend>{t.jobTypeFilter}</legend>
        <div className="home-board-checks">
          <label className="home-board-check">
            <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} />
            <span className="home-board-check-label">{t.remoteFilter}</span>
          </label>
          <label className="home-board-check">
            <input
              type="checkbox"
              checked={relocation}
              onChange={(e) => setRelocation(e.target.checked)}
            />
            <span className="home-board-check-label">{t.relocationFilter}</span>
          </label>
        </div>
      </fieldset>

      {categoryOptions.length ? (
        <fieldset className="home-board-filter-group">
          <legend>{t.categoryFilter}</legend>
          <div className="home-board-checks home-board-checks-scroll">
            {categoryOptions.map(({ name, total: count }) => (
              <label key={name} className="home-board-check">
                <input
                  type="checkbox"
                  checked={categories.includes(name)}
                  onChange={() => toggle(categories, setCategories, name)}
                />
                <span className="home-board-check-label">{categoryLabel(locale, name)}</span>
                <span className="home-board-check-count">{count}</span>
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}

      <div className="home-board-filter-group">
        <p className="home-board-filter-legend">{t.techStack}</p>
        <input
          type="search"
          className="home-board-filter-search"
          value={techQuery}
          placeholder={t.techPlaceholder}
          onChange={(e) => setTechQuery(e.target.value)}
        />
        {techOptions.length ? (
          <div className="home-board-checks home-board-checks-scroll">
            {techOptions.map(({ name, total: count }) => (
              <label key={name} className="home-board-check">
                <input
                  type="checkbox"
                  checked={stacks.includes(name)}
                  onChange={() => toggle(stacks, setStacks, name)}
                />
                <span className="home-board-check-label">{name}</span>
                <span className="home-board-check-count">{count}</span>
              </label>
            ))}
          </div>
        ) : null}
      </div>

      <div className="home-board-filter-group">
        <p className="home-board-filter-legend">{t.salaryMonthlyAz}</p>
        <div className="home-board-salary">
          <label>
            <span>{t.salaryFrom}</span>
            <input
              type="number"
              inputMode="numeric"
              min="0"
              step="1"
              value={salaryMin}
              placeholder={t.salaryFrom}
              onChange={(e) => setSalaryMin(e.target.value)}
            />
          </label>
          <label>
            <span>{t.salaryTo}</span>
            <input
              type="number"
              inputMode="numeric"
              min="0"
              step="1"
              value={salaryMax}
              placeholder={t.salaryTo}
              onChange={(e) => setSalaryMax(e.target.value)}
            />
          </label>
        </div>
        <p className="home-board-salary-note">{t.salaryNote}</p>
      </div>

      <div className="home-board-filter-group home-board-filter-more">
        <label className="stack">
          <span className="home-board-filter-legend">{t.companies}</span>
          <input
            type="search"
            value={company}
            placeholder={t.companyPlaceholder}
            onChange={(e) => setCompany(e.target.value)}
          />
        </label>
        <label className="stack">
          <span className="home-board-filter-legend">{t.when}</span>
          <select value={when} onChange={(e) => setWhen(e.target.value)}>
            <option value="any">{t.anyTime}</option>
            <option value="today">{t.today}</option>
            <option value="week">{t.week}</option>
          </select>
        </label>
      </div>

      <button type="button" className="home-board-reset" onClick={clear}>
        <ResetIcon />
        {t.resetFilters}
      </button>
    </>
  );
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
  const [q, setQ] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("q") || "";
  });
  const [draftQ, setDraftQ] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("q") || "";
  });
  const [company, setCompany] = useState("");
  const [city, setCity] = useState("");
  const [languages, setLanguages] = useState([]);
  const [remote, setRemote] = useState(false);
  const [relocation, setRelocation] = useState(false);
  const [onsite, setOnsite] = useState(false);
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
  const [reloadToken, setReloadToken] = useState(0);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filtersMounted, setFiltersMounted] = useState(false);
  const compact = useMediaQuery("(max-width: 959px)");
  const panelRef = useRef(null);
  const toggleRef = useRef(null);
  const closeRef = useRef(null);
  const resultsRef = useRef(null);
  const drawerExitRef = useRef(null);
  const skipFirstFetch = useRef(true);
  const prevTextKey = useRef(`${q}|${company}|${city}|${salaryMin}|${salaryMax}`);
  const prevFilterKey = useRef("");

  function openFilters() {
    if (drawerExitRef.current) {
      clearTimeout(drawerExitRef.current);
      drawerExitRef.current = null;
    }
    setFiltersMounted(true);
    setFiltersOpen(true);
  }

  function closeFilters() {
    setFiltersOpen(false);
    if (drawerExitRef.current) clearTimeout(drawerExitRef.current);
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    drawerExitRef.current = setTimeout(() => {
      setFiltersMounted(false);
      drawerExitRef.current = null;
    }, reduce ? DRAWER_EXIT_REDUCED_MS : DRAWER_EXIT_MS);
  }

  function retryLoad() {
    setLoadError(false);
    setReloadToken((n) => n + 1);
  }

  const filterKey = useMemo(
    () =>
      JSON.stringify({
        q,
        company,
        city,
        languages,
        remote,
        relocation,
        onsite,
        stacks,
        categories,
        when,
        sort,
        salaryMin,
        salaryMax,
      }),
    [q, company, city, languages, remote, relocation, onsite, stacks, categories, when, sort, salaryMin, salaryMax],
  );

  const boardTab = useMemo(() => {
    if (onsite && !remote && !relocation) return "company";
    if (remote && !relocation && !onsite) return "remote";
    if (relocation && !remote && !onsite) return "relocation";
    return "all";
  }, [remote, relocation, onsite]);

  function setBoardTab(next) {
    if (next === "remote") {
      setRemote(true);
      setRelocation(false);
      setOnsite(false);
      return;
    }
    if (next === "relocation") {
      setRemote(false);
      setRelocation(true);
      setOnsite(false);
      return;
    }
    if (next === "company") {
      setRemote(false);
      setRelocation(false);
      setOnsite(true);
      return;
    }
    setRemote(false);
    setRelocation(false);
    setOnsite(false);
  }

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
  const cityOptions = useMemo(() => {
    const list = Array.isArray(facetData.cities) ? facetData.cities : [];
    return list.slice(0, 12);
  }, [facetData]);
  const remoteTotal = Number(facetData.remote_total) || 0;
  const techOptions = useMemo(() => {
    const list = Array.isArray(facetData.stacks) ? facetData.stacks : [];
    const query = techQuery.trim().toLowerCase();
    return list.filter((item) => !query || String(item.name || "").toLowerCase().includes(query));
  }, [facetData, techQuery]);

  function toggle(list, setList, value) {
    setList(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  useEffect(() => {
    if (skipFirstFetch.current) {
      skipFirstFetch.current = false;
      prevFilterKey.current = filterKey;
      prevTextKey.current = `${q}|${company}|${city}|${salaryMin}|${salaryMax}`;
      if (!error && jobs.length > 0 && !q && !city && reloadToken === 0) return undefined;
    }
    if (prevFilterKey.current !== filterKey) {
      prevFilterKey.current = filterKey;
      if (page !== 1) {
        setPage(1);
        return undefined;
      }
    }
    const textKey = `${q}|${company}|${city}|${salaryMin}|${salaryMax}`;
    const textActive = Boolean(q.trim() || company.trim() || city.trim() || salaryMin.trim() || salaryMax.trim());
    const debounceMs = textKey !== prevTextKey.current && textActive ? TEXT_DEBOUNCE_MS : 0;
    prevTextKey.current = textKey;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const params = jobsListParams({
        page,
        perPage: PAGE_SIZE,
        q,
        company,
        city,
        remote,
        relocation,
        onsite,
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
    city,
    languages,
    remote,
    relocation,
    onsite,
    stacks,
    categories,
    when,
    sort,
    salaryMin,
    salaryMax,
    reloadToken,
  ]);

  useEffect(() => {
    return () => {
      if (drawerExitRef.current) clearTimeout(drawerExitRef.current);
    };
  }, []);

  function clear() {
    setLoading(true);
    setQ("");
    setDraftQ("");
    setCompany("");
    setCity("");
    setLanguages([]);
    setRemote(false);
    setRelocation(false);
    setOnsite(false);
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

  const activeChips = useMemo(() => {
    const chips = [];
    if (q.trim()) chips.push({ key: "q", label: q.trim(), onRemove: () => { setQ(""); setDraftQ(""); } });
    if (city.trim()) chips.push({ key: "city", label: city, onRemove: () => setCity("") });
    if (remote) chips.push({ key: "remote", label: t.placeRemote, onRemove: () => setRemote(false) });
    if (relocation) chips.push({ key: "relocation", label: t.relocationFilter, onRemove: () => setRelocation(false) });
    if (onsite) chips.push({ key: "onsite", label: t.tabCompanyPosted, onRemove: () => setOnsite(false) });
    for (const code of languages) {
      chips.push({
        key: `lang-${code}`,
        label: languageLabel(locale, code),
        onRemove: () => setLanguages((prev) => prev.filter((c) => c !== code)),
      });
    }
    for (const name of categories) {
      chips.push({
        key: `cat-${name}`,
        label: categoryLabel(locale, name),
        onRemove: () => setCategories((prev) => prev.filter((c) => c !== name)),
      });
    }
    for (const name of stacks) {
      chips.push({
        key: `stack-${name}`,
        label: name,
        onRemove: () => setStacks((prev) => prev.filter((c) => c !== name)),
      });
    }
    if (company.trim()) chips.push({ key: "company", label: company.trim(), onRemove: () => setCompany("") });
    if (when !== "any") {
      chips.push({
        key: "when",
        label: when === "today" ? t.today : t.week,
        onRemove: () => setWhen("any"),
      });
    }
    if (salaryMin.trim() || salaryMax.trim()) {
      chips.push({
        key: "salary",
        label: `${salaryMin || "…"}–${salaryMax || "…"}`,
        onRemove: () => {
          setSalaryMin("");
          setSalaryMax("");
        },
      });
    }
    return chips;
  }, [
    q,
    city,
    remote,
    relocation,
    onsite,
    languages,
    categories,
    stacks,
    company,
    when,
    salaryMin,
    salaryMax,
    locale,
    t,
  ]);

  const activeFilters = activeChips.length;
  const currentPage = Math.min(page, resultPages);

  useEffect(() => {
    if (!filtersMounted) return undefined;
    return lockBodyScroll();
  }, [filtersMounted]);

  useEffect(() => {
    if (!filtersOpen) return undefined;
    const toggleBtn = toggleRef.current;
    closeRef.current?.focus();
    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeFilters();
        return;
      }
      trapTab(event, panelRef.current);
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      toggleBtn?.focus({ preventScroll: true });
    };
  }, [filtersOpen]);

  function submitSearch(event) {
    event?.preventDefault?.();
    setQ(draftQ);
    const top = resultsRef.current?.getBoundingClientRect().top;
    if (typeof top === "number") {
      window.scrollTo({ top: window.scrollY + top - 72, behavior: "smooth" });
    }
  }

  function goToPage(next) {
    const clamped = Math.max(1, Math.min(resultPages, next));
    setPage(clamped);
    const top = resultsRef.current?.getBoundingClientRect().top;
    if (typeof top === "number") {
      window.scrollTo({ top: window.scrollY + top - 72, behavior: "smooth" });
    }
  }

  const filterProps = {
    t,
    locale,
    cityOptions,
    remoteTotal,
    languageOptions,
    categoryOptions,
    techOptions,
    techQuery,
    setTechQuery,
    city,
    setCity,
    languages,
    setLanguages,
    remote,
    setRemote: (value) => {
      const next = typeof value === "boolean" ? value : Boolean(value);
      setRemote(next);
      if (next) setOnsite(false);
    },
    relocation,
    setRelocation: (value) => {
      const next = typeof value === "boolean" ? value : Boolean(value);
      setRelocation(next);
      if (next) setOnsite(false);
    },
    categories,
    setCategories,
    stacks,
    setStacks,
    salaryMin,
    setSalaryMin,
    salaryMax,
    setSalaryMax,
    company,
    setCompany,
    when,
    setWhen,
    toggle,
    clear,
  };

  return (
    <Shell locale={locale} mode="browse">
      <div className="home home-board">
        {loadError ? (
          <div className="note home-board-load-error" role="alert">
            <p>{t.loadError}</p>
            <button type="button" className="btn home-board-load-retry" onClick={retryLoad}>
              {t.loadRetry}
            </button>
          </div>
        ) : null}

        <div className="home-board-shell">
          {!compact ? <BoardSideNav locale={locale} active="browse" /> : null}

          <div className="home-board-main">
            <div className="home-board-front">
              <section className="home-board-hero-copy" aria-labelledby="home-front-title">
                <p className="home-board-eyebrow">{t.jobBoardEyebrow}</p>
                <p className="home-board-brand">{t.homeBrand}</p>
                <h1 id="home-front-title" className="home-board-title">
                  {t.homeHeadline}
                </h1>
                <p className="home-board-lede">{t.openRolesLede}</p>
              </section>

              <BoardAcademyPromo locale={locale} />

              <form className="home-board-search" onSubmit={submitSearch} role="search">
                <label className="home-board-search-field home-board-search-q">
                  <SearchIcon />
                  <span className="visually-hidden">{t.searchKeywordPlaceholder}</span>
                  <input
                    type="search"
                    value={draftQ}
                    placeholder={t.searchKeywordPlaceholder}
                    onChange={(e) => setDraftQ(e.target.value)}
                  />
                </label>
                <label className="home-board-search-field">
                  <LocationIcon />
                  <span className="visually-hidden">{t.searchLocationPlaceholder}</span>
                  <select
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    aria-label={t.searchLocationPlaceholder}
                  >
                    <option value="">{t.searchLocationPlaceholder}</option>
                    {cityOptions.map(({ name }) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="home-board-search-field">
                  <LanguageIcon />
                  <span className="visually-hidden">{t.searchLanguagePlaceholder}</span>
                  <select
                    value={languages[0] || ""}
                    onChange={(e) => setLanguages(e.target.value ? [e.target.value] : [])}
                    aria-label={t.searchLanguagePlaceholder}
                  >
                    <option value="">{t.searchLanguagePlaceholder}</option>
                    {languageOptions.map((code) => (
                      <option key={code} value={code}>
                        {languageLabel(locale, code)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="home-board-search-field">
                  <CategoryIcon />
                  <span className="visually-hidden">{t.searchCategoryPlaceholder}</span>
                  <select
                    value={categories[0] || ""}
                    onChange={(e) => setCategories(e.target.value ? [e.target.value] : [])}
                    aria-label={t.searchCategoryPlaceholder}
                  >
                    <option value="">{t.searchCategoryPlaceholder}</option>
                    {categoryOptions.map(({ name }) => (
                      <option key={name} value={name}>
                        {categoryLabel(locale, name)}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  ref={toggleRef}
                  type="button"
                  className="home-board-more"
                  aria-haspopup="dialog"
                  aria-expanded={filtersOpen}
                  aria-controls="job-filters"
                  onClick={openFilters}
                >
                  <FilterIcon />
                  <span className="home-board-more-label">{t.moreFilters}</span>
                  {activeFilters ? <span className="filters-badge">{activeFilters}</span> : null}
                </button>
                <button type="submit" className="btn primary home-board-search-submit">
                  {t.searchSubmit}
                </button>
              </form>
            </div>

            {activeChips.length ? (
              <div className="home-board-chips" role="list" aria-label={t.filters}>
                {activeChips.map((chip) => (
                  <button
                    key={chip.key}
                    type="button"
                    className="home-board-chip"
                    role="listitem"
                    onClick={chip.onRemove}
                  >
                    {chip.label}
                    <span aria-hidden="true"> ×</span>
                  </button>
                ))}
                <button type="button" className="home-board-clear-all" onClick={clear}>
                  {t.clearAll}
                </button>
              </div>
            ) : null}

            <div className="home-board-tabs" role="tablist" aria-label={t.categoryTabsLabel}>
              {[
                { id: "all", label: t.tabAll },
                { id: "remote", label: t.tabRemote },
                { id: "relocation", label: t.tabRelocation },
                { id: "company", label: t.tabCompanyPosted },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={boardTab === tab.id}
                  className={`home-board-tab${boardTab === tab.id ? " on" : ""}`}
                  onClick={() => setBoardTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <section
              className="home-board-results"
              ref={resultsRef}
              aria-labelledby="results-heading"
              aria-busy={loading || undefined}
            >
              <div className="home-board-results-head">
                <div className="home-board-results-titles">
                  <p className="home-board-catalogue-kicker">{t.openRoles}</p>
                  <h2 id="results-heading" className="home-board-results-count" key={resultTotal}>
                    {t.resultsCount(resultTotal)}
                  </h2>
                </div>
                <label className="home-board-sort">
                  <span className="visually-hidden">{t.sort}</span>
                  <select value={sort} onChange={(e) => setSort(e.target.value)}>
                    <option value="newest">{t.newestFirst}</option>
                    <option value="oldest">{t.oldest}</option>
                    <option value="title">{t.byTitle}</option>
                  </select>
                </label>
              </div>

              <p className="visually-hidden" aria-live="polite" aria-atomic="true">
                {loading ? t.listLoading : ""}
              </p>

              {!loading && resultTotal === 0 && !loadError ? (
                <div className="job-empty">
                  <p className="job-empty-copy">{t.empty}</p>
                  {activeFilters > 0 ? (
                    <button type="button" className="btn job-empty-clear" onClick={clear}>
                      {t.clear}
                    </button>
                  ) : null}
                </div>
              ) : null}

              {loading ? (
                <div className="home-board-card-list is-loading">
                  {Array.from({ length: 5 }, (_, index) => (
                    <div key={index} className="job-board-card job-board-card-skeleton" aria-hidden="true">
                      <div className="job-board-card-main">
                        <span className="skeleton job-board-skel-logo" />
                        <div className="job-board-card-body">
                          <span className="skeleton skeleton-line short" />
                          <span className="skeleton skeleton-line" />
                          <span className="skeleton skeleton-line short" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="home-board-card-list">
                  {items.map((job) => (
                    <JobBoardCard key={job.id} locale={locale} job={job} />
                  ))}
                </div>
              )}

              {resultTotal > PAGE_SIZE ? (
                <nav className="home-board-pager pager" aria-label={t.pageOf(currentPage, resultPages)}>
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

          {!compact ? (
            <aside className="home-board-sidebar" aria-label={t.filters}>
              <FilterPanelBody {...filterProps} />
            </aside>
          ) : null}
        </div>

        {filtersMounted ? (
          <>
            <div
              className={`filter-backdrop ${filtersOpen ? "is-open" : "is-closing"}`}
              aria-hidden="true"
              onClick={closeFilters}
            />
            <aside
              ref={panelRef}
              id="job-filters"
              className={`home-board-drawer ${filtersOpen ? "is-open" : "is-closing"}`}
              role="dialog"
              aria-modal="true"
              aria-labelledby="job-filters-title"
            >
              <div className="home-board-drawer-head">
                <h2 id="job-filters-title">{t.filters}</h2>
                <button
                  ref={closeRef}
                  type="button"
                  className="filter-close"
                  aria-label={t.filtersClose}
                  onClick={closeFilters}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                    <path d="M6 6l12 12M18 6L6 18" />
                  </svg>
                </button>
              </div>
              <div className="home-board-drawer-body">
                <FilterPanelBody {...filterProps} />
              </div>
              <div className="home-board-drawer-actions">
                <button type="button" className="btn" onClick={clear}>
                  {t.filtersClear}
                </button>
                <button type="button" className="btn primary" onClick={closeFilters}>
                  {t.filtersApply}
                </button>
              </div>
            </aside>
          </>
        ) : null}
      </div>
    </Shell>
  );
}
