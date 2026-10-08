"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { refreshSavedJobs, unsaveJob } from "../lib/server/refresh";
import { JobCard } from "./job-card";
import { useInitialMe } from "./me-seed";
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
        <div className="applications-page">
          <header className="applications-head">
            <h1>{t.savedJobs}</h1>
            <p className="lede">{t.savedJobsLede}</p>
          </header>
          {error ? <p className="note">{error}</p> : null}
          {items.length === 0 ? <p className="empty-line">{t.savedJobsEmpty}</p> : null}
          <div className="job-list saved-job-list">
            {items.map((job) => (
              <div key={job.id} className="saved-job-row">
                <JobCard locale={locale} job={job} />
                <button type="button" className="text-btn" onClick={() => remove(job.id)}>
                  {t.unsaveJob}
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <section className="applications-page applications-gate">
          <header className="applications-head">
            <h1>{t.savedJobs}</h1>
            <p className="lede">{t.savedJobsGate}</p>
          </header>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "saved" })} />
        </section>
      )}
    </Shell>
  );
}
