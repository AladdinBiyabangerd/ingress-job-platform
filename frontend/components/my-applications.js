"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { ApplicationList } from "./application-list";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

export function MyApplications({ locale }) {
  const t = text(locale);
  const [me, setMe] = useState(undefined);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  const allowed = Boolean(me?.authenticated && (me.candidate || me.staff));

  async function load() {
    const res = await fetch("/api/auth/applications", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error("load");
    setItems(Array.isArray(data.items) ? data.items : []);
  }

  useEffect(() => {
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
  }, []);

  useEffect(() => {
    if (!allowed) return undefined;
    let cancelled = false;
    load().catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [allowed, t.loadError]);

  return (
    <Shell locale={locale} mode="applications">
      {me === undefined ? null : allowed ? (
        <div className="applications-page">
          <header className="applications-head">
            <h1>{t.myApplications}</h1>
            <p className="lede">{t.myApplicationsLede}</p>
          </header>
          {error ? <p className="note">{error}</p> : null}
          <ApplicationList locale={locale} items={items} mode="candidate" onChanged={load} />
        </div>
      ) : (
        <section className="applications-page applications-gate">
          <header className="applications-head">
            <h1>{t.myApplications}</h1>
            <p className="lede">{t.applicationsGate}</p>
          </header>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "applications" })} />
        </section>
      )}
    </Shell>
  );
}
