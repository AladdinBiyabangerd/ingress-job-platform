"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { Admin } from "./admin";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

export function AdminPage({
  locale,
  initialJobs = null,
  initialApplications = null,
  initialCrawled = null,
  initialAiFlags = null,
}) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });

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

  const isStaff = Boolean(me?.authenticated && me.staff);

  return (
    <Shell locale={locale} mode="admin">
      {me === undefined ? null : isStaff ? (
        <Admin
          locale={locale}
          initialJobs={initialJobs}
          initialApplications={initialApplications}
          initialCrawled={initialCrawled}
          initialAiFlags={initialAiFlags}
        />
      ) : (
        <div className="h2-employer">
          <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={t.adminTitle} />
          <div className="h2-empty h2-gate">
            <p>{t.adminGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "admin" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}
