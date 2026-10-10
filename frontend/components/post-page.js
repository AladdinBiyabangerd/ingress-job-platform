"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { canPostJobs, isCandidateOnly } from "../lib/roles";
import { Cabinet } from "./cabinet";
import { LoginLink } from "./login-link";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { Shell } from "./shell";

export function PostPage({ locale, initialJobs = null, initialApplications = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [employerDenied, setEmployerDenied] = useState(false);

  useEffect(() => {
    setEmployerDenied(new URLSearchParams(window.location.search).get("employer_denied") === "1");
  }, []);

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
  const companyReturn = hrefFor(locale, { mode: "company" });
  const postReturn = hrefFor(locale, { mode: "post" });

  return (
    <Shell locale={locale} mode="post">
      {me === undefined ? null : canPost ? (
        <Cabinet locale={locale} me={me} initialJobs={initialJobs} initialApplications={initialApplications} />
      ) : isCandidateOnly(me) ? (
        <div className="h2-employer post-cabinet">
          <PageChrome
            className="post-cabinet-chrome"
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.postCandidateTitle}
          />
          <div className="h2-panel post-cabinet-gate">
            <p>{t.postCandidateBody}</p>
            {employerDenied ? <p className="note" role="alert">{t.postEmployerDenied}</p> : null}
            <div className="post-cabinet-gate-actions">
              <a className="btn small" href={hrefFor(locale)}>{t.postBackToJobs}</a>
              <LoginLink className="btn small primary" intent="job_employer" returnTo={companyReturn}>
                {t.postBecomeEmployer}
              </LoginLink>
            </div>
          </div>
        </div>
      ) : (
        <div className="h2-employer post-cabinet">
          <PageChrome
            className="post-cabinet-chrome"
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.postTitle}
          />
          <div className="h2-panel post-cabinet-gate">
            <p>{t.postBody}</p>
            <div className="post-cabinet-gate-actions">
              <LoginLink className="btn small board-auth-signin" intent="job_employer" returnTo={postReturn}>
                {t.signIn}
              </LoginLink>
              <LoginLink className="btn small primary" intent="job_employer" returnTo={companyReturn}>
                {t.createAccount}
              </LoginLink>
            </div>
          </div>
        </div>
      )}
    </Shell>
  );
}
