"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { refreshMyApplications } from "../lib/server/refresh";
import { ApplicationsBoard } from "./applications-board";
import { LoginLink } from "./login-link";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
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
  const returnTo = hrefFor(locale, { mode: "applications" });

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
        <div className="h2-candidate my-applications">
          <PageChrome
            className="my-applications-chrome"
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.myApplications}
            count={items.length || undefined}
          />
          {error ? <p className="note apps-e-banner">{error}</p> : null}
          <ApplicationsBoard locale={locale} items={items} onChanged={load} />
        </div>
      ) : (
        <div className="h2-candidate my-applications">
          <PageChrome
            className="my-applications-chrome"
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.myApplications}
          />
          <div className="h2-panel my-applications-gate">
            <p>{t.applicationsGate}</p>
            <div className="my-applications-gate-actions">
              <LoginLink className="btn small board-auth-signin" intent="job_candidate" returnTo={returnTo}>
                {t.signIn}
              </LoginLink>
              <LoginLink className="btn small primary" intent="job_candidate" returnTo={returnTo}>
                {t.createAccount}
              </LoginLink>
            </div>
          </div>
        </div>
      )}
    </Shell>
  );
}
