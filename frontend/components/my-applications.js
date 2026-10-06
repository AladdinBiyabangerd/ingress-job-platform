"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { refreshMyApplications } from "../lib/server/refresh";
import { ApplicationList } from "./application-list";
import { useInitialMe } from "./me-seed";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

export function MyApplications({ locale, initialItems = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const seededList = Array.isArray(initialItems);
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [items, setItems] = useState(() => (seededList ? initialItems : []));
  const [error, setError] = useState("");

  const allowed = Boolean(me?.authenticated && (me.candidate || me.staff));

  async function load() {
    setItems(await refreshMyApplications());
  }

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe.authenticated ? initialMe : null);
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
    if (!allowed) return undefined;
    if (seededList) return undefined;
    let cancelled = false;
    load().catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [allowed, seededList, t.loadError]);

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
