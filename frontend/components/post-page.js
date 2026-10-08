"use client";

import { useEffect, useState } from "react";
import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { canPostJobs, isCandidateOnly } from "../lib/roles";
import { Cabinet } from "./cabinet";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

export function PostPage({ locale, initialJobs = null, initialApplications = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });

  useEffect(() => {
    function applyMe(data) {
      if (data?.needs_company_profile) {
        window.location.href = hrefFor(locale, { mode: "company" });
        return;
      }
      setMe(data);
    }
    if (initialMe && typeof initialMe === "object") {
      applyMe(initialMe.authenticated ? initialMe : null);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) applyMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [initialMe, locale]);

  const canPost = canPostJobs(me) && !me.needs_company_profile;
  const back = hrefFor(locale, { mode: "post" });

  return (
    <Shell locale={locale} mode="post">
      {me === undefined ? null : canPost ? (
        <Cabinet locale={locale} me={me} initialJobs={initialJobs} initialApplications={initialApplications} />
      ) : isCandidateOnly(me) ? (
        <div className="h2-employer">
          <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={t.postCandidateTitle} />
          <div className="h2-empty h2-gate">
            <p>{t.postCandidateBody}</p>
            <div className="h2-gate-actions">
              <a className="btn ink" href={hrefFor(locale)}>{t.postBackToJobs}</a>
              <a className="btn" href={loginHref({ intent: "job_employer", returnTo: back })}>{t.postBecomeEmployer}</a>
            </div>
          </div>
        </div>
      ) : (
        <div className="h2-employer">
          <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={t.postTitle} />
          <div className="h2-empty h2-gate">
            <p>{t.postBody}</p>
            <RegisterChoice locale={locale} returnTo={back} />
          </div>
        </div>
      )}
    </Shell>
  );
}
