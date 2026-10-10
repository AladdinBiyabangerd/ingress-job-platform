"use client";

import { useEffect, useState } from "react";
import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { refreshSavedJobs, unsaveJob } from "../lib/server/refresh";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { preloadSavedIds } from "./save-job-button";
import { SavedJobListItem, SavedJobPreview } from "./saved-job-panel";
import { Shell } from "./shell";

const PER_PAGE = 20;

export function MySaved({
  locale,
  initialItems = null,
  initialIds = null,
  initialTotal = null,
  initialPages = null,
}) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const seededList = Array.isArray(initialItems);
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [items, setItems] = useState(() => (seededList ? initialItems : []));
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(() =>
    typeof initialPages === "number" ? initialPages : seededList && initialItems.length ? 1 : 0,
  );
  const [total, setTotal] = useState(() =>
    typeof initialTotal === "number" ? initialTotal : seededList ? initialItems.length : 0,
  );
  const [selectedId, setSelectedId] = useState(() =>
    seededList && initialItems[0] ? initialItems[0].id : null,
  );
  const [mobileDetail, setMobileDetail] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
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
    refreshSavedJobs(1, PER_PAGE)
      .then((data) => {
        if (cancelled) return;
        const next = Array.isArray(data.items) ? data.items : [];
        setItems(next);
        setPage(Number(data.page) || 1);
        setPages(Number(data.pages) || 0);
        setTotal(Number(data.total) || next.length);
        setSelectedId(next[0]?.id ?? null);
        setMobileDetail(false);
      })
      .catch(() => {
        if (!cancelled) setError(t.loadError);
      });
    return () => {
      cancelled = true;
    };
  }, [allowed, seededList, t.loadError]);

  useEffect(() => {
    if (!items.length) {
      setSelectedId(null);
      return;
    }
    if (!items.some((job) => job.id === selectedId)) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  const selected = items.find((job) => job.id === selectedId) || null;

  function selectJob(jobId) {
    setSelectedId(jobId);
    setMobileDetail(true);
  }

  function backToList() {
    setMobileDetail(false);
  }

  async function remove(jobId) {
    const result = await unsaveJob(jobId);
    if (!result.ok) {
      setError(t.saveJobError);
      return;
    }
    const idx = items.findIndex((job) => job.id === jobId);
    const next = items.filter((job) => job.id !== jobId);
    setItems(next);
    setTotal((n) => Math.max(0, Number(n) - 1));
    if (selectedId === jobId) {
      const neighbor = next[idx] || next[idx - 1] || null;
      setSelectedId(neighbor?.id ?? null);
      if (!neighbor) setMobileDetail(false);
    }
  }

  async function loadMore() {
    if (loadingMore || page >= pages) return;
    setLoadingMore(true);
    setError("");
    try {
      const data = await refreshSavedJobs(page + 1, PER_PAGE);
      const more = Array.isArray(data.items) ? data.items : [];
      setItems((prev) => {
        const seen = new Set(prev.map((job) => job.id));
        return [...prev, ...more.filter((job) => !seen.has(job.id))];
      });
      setPage(Number(data.page) || page + 1);
      setPages(Number(data.pages) || pages);
      setTotal(Number(data.total) || total);
    } catch {
      setError(t.loadError);
    } finally {
      setLoadingMore(false);
    }
  }

  const count = total || items.length || undefined;
  const canLoadMore = page < pages;
  const returnTo = hrefFor(locale, { mode: "saved" });

  return (
    <Shell locale={locale} mode="saved">
      {me === undefined ? null : allowed ? (
        <div className="h2-candidate my-saved">
          <PageChrome
            className="my-saved-chrome"
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.savedJobs}
            count={count}
          />
          {error ? <p className="note my-saved-banner">{error}</p> : null}
          {items.length === 0 ? (
            <div className="my-saved-empty">
              <p>{t.savedJobsEmpty}</p>
            </div>
          ) : (
            <div className={["saved-split", mobileDetail ? "is-mobile-detail" : ""].filter(Boolean).join(" ")}>
              <div className="saved-list-pane">
                <div className="saved-list" aria-label={t.savedJobs}>
                  {items.map((job) => (
                    <SavedJobListItem
                      key={job.id}
                      locale={locale}
                      job={job}
                      selected={job.id === selectedId}
                      onSelect={selectJob}
                    />
                  ))}
                </div>
                {canLoadMore ? (
                  <div className="saved-list-more">
                    <button type="button" className="btn small" disabled={loadingMore} onClick={loadMore}>
                      {t.savedJobsLoadMore}
                    </button>
                  </div>
                ) : null}
              </div>
              <div className="saved-preview-pane">
                {selected ? (
                  <SavedJobPreview
                    locale={locale}
                    job={selected}
                    onUnsave={remove}
                    onBack={mobileDetail ? backToList : null}
                  />
                ) : null}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="h2-candidate my-saved">
          <PageChrome
            className="my-saved-chrome"
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.savedJobs}
          />
          <div className="h2-panel my-saved-gate">
            <p>{t.savedJobsGate}</p>
            <div className="my-saved-gate-actions">
              <a
                className="btn small board-auth-signin"
                href={loginHref({ intent: "job_candidate", returnTo })}
              >
                {t.signIn}
              </a>
              <a
                className="btn small primary"
                href={loginHref({ intent: "job_candidate", returnTo })}
              >
                {t.createAccount}
              </a>
            </div>
          </div>
        </div>
      )}
    </Shell>
  );
}
