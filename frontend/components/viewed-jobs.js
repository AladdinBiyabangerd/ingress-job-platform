"use client";

import { useEffect, useState } from "react";
import { fetchMe } from "../lib/me-client";
import { markJobViewed } from "../lib/server/refresh";
import { useInitialMe } from "./me-seed";

let idsCache = null;
let idsPromise = null;
const listeners = new Set();

function notify(ids) {
  idsCache = ids;
  for (const fn of listeners) fn(ids);
}

export function preloadViewedIds(ids) {
  if (Array.isArray(ids)) notify(new Set(ids.map((id) => Number(id)).filter((id) => id > 0)));
}

async function ensureIds() {
  if (idsCache) return idsCache;
  if (!idsPromise) {
    idsPromise = fetch("/api/auth/viewed-jobs/ids", { credentials: "same-origin", cache: "no-store" })
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

/** True when the signed-in user has opened this job detail before. */
export function useJobViewed(jobId) {
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [viewed, setViewed] = useState(() => (idsCache ? idsCache.has(Number(jobId)) : false));

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
      setViewed(ids.has(Number(jobId)));
    }
    listeners.add(onChange);
    if (me?.authenticated) {
      ensureIds().then(onChange);
    }
    return () => {
      listeners.delete(onChange);
    };
  }, [jobId, me?.authenticated]);

  return viewed;
}

/** Record a detail view once the candidate is signed in. */
export function useMarkJobViewed(jobId, { enabled = true } = {}) {
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });

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
    if (!enabled || !me?.authenticated) return undefined;
    const id = Number(jobId);
    if (!Number.isInteger(id) || id <= 0) return undefined;
    let cancelled = false;
    (async () => {
      const result = await markJobViewed(id);
      if (cancelled || !result.ok) return;
      const next = new Set(idsCache || []);
      next.add(id);
      notify(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [jobId, me?.authenticated, enabled]);
}
