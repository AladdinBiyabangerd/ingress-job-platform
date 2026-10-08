"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { refreshSavedJobs, unsaveJob } from "../lib/server/refresh";
import { JobRow } from "./job-row";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { preloadSavedIds } from "./save-job-button";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

export function MySaved({ locale, initialItems = null, initialIds = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const seededList = Array.isArray(initialItems);
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [items, setItems] = useState(() => (seededList ? initialItems : []));
  const [error, setError] = useState("");

  useEffect(() => {
    if (Array.isArray(initialIds)) preloadSavedIds(initialIds);
  }, [initialIds]);

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

  const allowed = Boolean(me?.authenticated);

  useEffect(() => {
    if (!allowed) return undefined;
    if (seededList) return undefined;
    let cancelled = false;
    refreshSavedJobs()
      .then((data) => {
        if (!cancelled) setItems(Array.isArray(data.items) ? data.items : []);
      })
      .catch(() => {
        if (!cancelled) setError(t.loadError);
      });
    return () => {
      cancelled = true;
    };
  }, [allowed, seededList, t.loadError]);

  async function remove(jobId) {
    const result = await unsaveJob(jobId);
    if (!result.ok) {
      setError(t.saveJobError);
      return;
    }
    setItems((prev) => prev.filter((job) => job.id !== jobId));
  }

  return (
    <Shell locale={locale} mode="saved">
      {me === undefined ? null : allowed ? (
        <div className="h2-candidate">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.savedJobs}
            count={items.length || undefined}
          />
          {error ? <p className="note">{error}</p> : null}
          {items.length === 0 ? (
            <div className="h2-empty">
              <p>{t.savedJobsEmpty}</p>
            </div>
          ) : (
            <div className="job-row-list saved-job-list">
              {items.map((job) => (
                <JobRow
                  key={job.id}
                  locale={locale}
                  job={job}
                  showSave={false}
                  leading={
                    <button type="button" className="text-btn" onClick={() => remove(job.id)}>
                      {t.unsaveJob}
                    </button>
                  }
                />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="h2-candidate">
          <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={t.savedJobs} />
          <div className="h2-empty h2-gate">
            <p>{t.savedJobsGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "saved" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}
