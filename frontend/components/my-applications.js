"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { refreshMyApplications } from "../lib/server/refresh";
import { ApplicationList } from "./application-list";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
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
        <div className="h2-candidate">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.myApplications}
            count={items.length || undefined}
          />
          {error ? <p className="note">{error}</p> : null}
          <div className="h2-panel h2-candidate-list">
            <ApplicationList locale={locale} items={items} mode="candidate" onChanged={load} />
          </div>
        </div>
      ) : (
        <div className="h2-candidate">
          <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={t.myApplications} />
          <div className="h2-empty h2-gate">
            <p>{t.applicationsGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "applications" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}
