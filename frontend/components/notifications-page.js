"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { markAllNotificationsRead, markNotificationRead, refreshNotifications } from "../lib/server/refresh";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { Pager } from "./pager";
import { useInitialMe } from "./me-seed";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

const LINES = {
  application_new: "noteApplicationNew",
  application_seen: "noteApplicationSeen",
  application_rejected: "noteApplicationRejected",
  ad_approved: "noteAdApproved",
  ad_rejected: "noteAdRejected",
  ad_review: "noteAdReview",
};

function destination(locale, item) {
  if (item.kind === "application_seen" || item.kind === "application_rejected") {
    return hrefFor(locale, { mode: "applications" });
  }
  if (item.kind === "application_new" || item.kind === "ad_approved" || item.kind === "ad_rejected" || item.kind === "ad_review") {
    return hrefFor(locale, { mode: "post" });
  }
  return hrefFor(locale);
}

export function NotificationsPage({ locale, initialItems = null, initialUnread = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const seededList = Array.isArray(initialItems);
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [items, setItems] = useState(() => (seededList ? initialItems : []));
  const [unread, setUnread] = useState(() => (seededList ? Number(initialUnread) || 0 : 0));
  const [error, setError] = useState("");
  const { pageItems, currentPage, totalPages, pageSize, total, goToPage } = usePagination(items, LIST_PAGE_SIZE);

  async function load() {
    const data = await refreshNotifications();
    setItems(data.items);
    setUnread(data.unread);
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
    if (!me?.authenticated) return undefined;
    if (seededList) return undefined;
    let cancelled = false;
    load().catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [me, seededList, t.loadError]);

  async function markOne(id) {
    const res = await markNotificationRead(id);
    if (!res.ok) {
      setError(t.loadError);
      return;
    }
    await load().catch(() => setError(t.loadError));
  }

  async function markAll() {
    const res = await markAllNotificationsRead();
    if (!res.ok) {
      setError(t.loadError);
      return;
    }
    await load().catch(() => setError(t.loadError));
  }

  const signedIn = Boolean(me?.authenticated);

  return (
    <Shell locale={locale} mode="notifications">
      <section className="cabinet">
        <h1>{t.notificationsTitle}</h1>
      </section>
      {me === undefined ? null : !signedIn ? (
        <div className="empty">
          <p className="lede">{t.notificationsGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "notifications" })} />
        </div>
      ) : (
        <div className="notice-list">
          {error ? <p className="note">{error}</p> : null}
          {unread > 0 ? (
            <button type="button" className="text-btn" onClick={markAll}>
              {t.markAllRead}
            </button>
          ) : null}
          {items.length === 0 ? <p>{t.notificationsEmpty}</p> : null}
          {pageItems.map((item) => {
            const key = LINES[item.kind];
            const line = key && typeof t[key] === "function" ? t[key](item.job_title || "") : item.job_title;
            return (
              <article key={item.id} className={item.read ? "notice" : "notice unread"}>
                <a href={destination(locale, item)}>{line}</a>
                {item.reason ? (
                  <p className="notice-reason">
                    {t.rejectReason}: {item.reason}
                  </p>
                ) : null}
                {item.read ? null : (
                  <button type="button" className="text-btn" onClick={() => markOne(item.id)}>
                    {t.markRead}
                  </button>
                )}
              </article>
            );
          })}
          <Pager
            locale={locale}
            currentPage={currentPage}
            totalPages={totalPages}
            total={total}
            pageSize={pageSize}
            onPageChange={goToPage}
          />
        </div>
      )}
    </Shell>
  );
}
