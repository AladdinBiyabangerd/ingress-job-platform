"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

function TalentCard({ locale, item }) {
  const t = text(locale);
  const skills = Array.isArray(item.skills) ? item.skills : [];
  const place = [item.city, item.country].filter(Boolean).join(", ");
  const years =
    typeof item.total_years === "number" && Number.isFinite(item.total_years)
      ? t.talentYears(item.total_years)
      : "";
  return (
    <article className="h2-talent-row">
      <header className="h2-talent-row-top">
        <h2>{item.visibility === "public" && item.display_name ? item.display_name : t.talentAnonymous}</h2>
        {item.visibility === "anonymous" ? (
          <span className="source-pill">{t.talentVisibilityAnonymous}</span>
        ) : (
          <span className="source-pill">{t.talentVisibilityPublic}</span>
        )}
      </header>
      {item.headline ? <p className="talent-headline">{item.headline}</p> : null}
      <p className="talent-meta">
        {item.seniority ? <span>{item.seniority}</span> : null}
        {years ? <span>{years}</span> : null}
        {place ? <span>{place}</span> : null}
      </p>
      {skills.length ? (
        <ul className="tech-chips" aria-label={t.techStack}>
          {skills.map((name) => (
            <li key={name} className="tech-chip">
              {name}
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export function TalentSearch({ locale, initial = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const seeded = initial && typeof initial === "object";
  const [me, setMe] = useState(() => {
    if (seeded?.me) return seeded.me;
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [q, setQ] = useState(() => (seeded ? seeded.q || "" : ""));
  const [items, setItems] = useState(() => (seeded && Array.isArray(seeded.items) ? seeded.items : []));
  const [gate, setGate] = useState(() => (seeded ? seeded.gate : null));
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (seeded?.me) {
      setMe(seeded.me);
      return undefined;
    }
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
  }, [initialMe, seeded]);

  async function runSearch(nextQ) {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ page: "1", per_page: "20" });
      const query = (nextQ || "").trim();
      if (query) params.set("q", query);
      const res = await fetch(`/api/auth/talent?${params}`, {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (res.status === 401) {
        setGate("guest");
        setItems([]);
        return;
      }
      if (res.status === 403) {
        setGate(me?.needs_company_profile ? "company" : "role");
        setItems([]);
        return;
      }
      if (!res.ok) {
        setError(t.loadError);
        return;
      }
      const data = await res.json();
      setGate(null);
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setError(t.loadError);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    runSearch(q);
  }

  const resolvedGate =
    gate ||
    (!me?.authenticated
      ? "guest"
      : !(me.employer || me.staff)
        ? "role"
        : me.needs_company_profile
          ? "company"
          : null);

  return (
    <Shell locale={locale} mode="talent">
      <div className="h2-employer">
        <PageChrome
          backHref={hrefFor(locale)}
          backLabel={t.breadcrumbHome}
          title={t.talentTitle}
          count={resolvedGate ? undefined : items.length || undefined}
        />
        <p className="hint h2-employer-hint" title={t.talentLede}>{t.talentLede}</p>

        {me === undefined ? null : resolvedGate === "guest" ? (
          <div className="h2-empty h2-gate">
            <p>{t.talentGateGuest}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "talent" })} />
          </div>
        ) : resolvedGate === "role" ? (
          <div className="h2-empty">
            <p className="note">{t.talentGateRole}</p>
          </div>
        ) : resolvedGate === "company" ? (
          <div className="h2-empty">
            <p className="note">
              {t.talentGateCompany}{" "}
              <a href={hrefFor(locale, { mode: "company" })}>{t.profileOpen}</a>
            </p>
          </div>
        ) : (
          <>
            <form className="h2-tools" onSubmit={onSubmit}>
              <label className="visually-hidden" htmlFor="talent-q">
                {t.talentSearchLabel}
              </label>
              <div className="h2-tools-search">
                <input
                  id="talent-q"
                  type="search"
                  value={q}
                  onChange={(event) => setQ(event.target.value)}
                  placeholder={t.talentSearchPlaceholder}
                  maxLength={120}
                />
              </div>
              <button type="submit" className="btn ink" disabled={loading}>
                {t.talentSearch}
              </button>
            </form>
            {error ? <p className="note">{error}</p> : null}
            <div className="h2-panel h2-employer-list">
              {!loading && items.length === 0 ? <p className="empty-line">{t.talentEmpty}</p> : null}
              <div className="h2-talent-list">
                {items.map((item) => (
                  <TalentCard key={item.id} locale={locale} item={item} />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
