"use client";

import { useEffect, useState } from "react";
import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { saveJob, unsaveJob } from "../lib/server/refresh";
import { useInitialMe } from "./me-seed";

let idsCache = null;
let idsPromise = null;
const listeners = new Set();

function notify(ids) {
  idsCache = ids;
  for (const fn of listeners) fn(ids);
}

export function preloadSavedIds(ids) {
  if (Array.isArray(ids)) notify(new Set(ids.map((id) => Number(id)).filter((id) => id > 0)));
}

async function ensureIds() {
  if (idsCache) return idsCache;
  if (!idsPromise) {
    idsPromise = fetch("/api/auth/saved-jobs/ids", { credentials: "same-origin", cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) return new Set();
        const data = await res.json().catch(() => ({}));
        const ids = Array.isArray(data.ids) ? data.ids.map((id) => Number(id)).filter((id) => id > 0) : [];
        return new Set(ids);
      })
      .catch(() => new Set())
      .finally(() => {
        idsPromise = null;
      });
  }
  const set = await idsPromise;
  notify(set);
  return set;
}

export function SaveJobButton({ locale, jobId, returnTo, className = "", icon = "star", showLabel = false }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [saved, setSaved] = useState(() => (idsCache ? idsCache.has(Number(jobId)) : false));
  const [busy, setBusy] = useState(false);
  const bookmark = icon === "bookmark";

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe);
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
    function onChange(ids) {
      setSaved(ids.has(Number(jobId)));
    }
    listeners.add(onChange);
    if (me?.authenticated) {
      ensureIds().then(onChange);
    }
    return () => {
      listeners.delete(onChange);
    };
  }, [jobId, me?.authenticated]);

  const back = returnTo || hrefFor(locale, { jobId });

  async function toggle(event) {
    event.preventDefault();
    event.stopPropagation();
    if (!me?.authenticated) {
      window.location.href = loginHref({ returnTo: back });
      return;
    }
    if (busy) return;
    setBusy(true);
    const next = !saved;
    setSaved(next);
    const nextSet = new Set(idsCache || []);
    if (next) nextSet.add(Number(jobId));
    else nextSet.delete(Number(jobId));
    notify(nextSet);
    try {
      const result = next ? await saveJob(jobId) : await unsaveJob(jobId);
      if (!result.ok) {
        setSaved(!next);
        const revert = new Set(idsCache || []);
        if (next) revert.delete(Number(jobId));
        else revert.add(Number(jobId));
        notify(revert);
      }
    } catch {
      setSaved(!next);
    } finally {
      setBusy(false);
    }
  }

  const label = saved ? t.unsaveJob : t.jdSave || t.saveJob;

  return (
    <button
      type="button"
      className={`save-job-btn${bookmark ? " save-job-btn-bookmark" : ""}${saved ? " on" : ""}${showLabel ? " save-job-btn-labeled" : ""}${className ? ` ${className}` : ""}`}
      aria-pressed={saved}
      aria-label={saved ? t.unsaveJob : t.saveJob}
      title={saved ? t.unsaveJob : t.saveJob}
      disabled={busy}
      onClick={toggle}
    >
      {bookmark ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
          <path
            d="M7 3.5h10a1 1 0 011 1V21l-6-3.5L6 21V4.5a1 1 0 011-1z"
            fill={saved ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <path
            d="M8 2.6 9.7 6l3.7.3-2.8 2.5.9 3.6L8 10.7 4.5 12.4l.9-3.6L2.6 6.3 6.3 6 8 2.6z"
            fill={saved ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
        </svg>
      )}
      {showLabel ? <span className="save-job-btn-text">{label}</span> : null}
    </button>
  );
}
