"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { Pager } from "./pager";
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

export function NotificationsPage({ locale }) {
  const t = text(locale);
  const [me, setMe] = useState(undefined);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState("");
  const { pageItems, currentPage, totalPages, pageSize, total, goToPage } = usePagination(items, LIST_PAGE_SIZE);

  async function load() {
    const res = await fetch("/api/auth/notifications", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error("load");
    setItems(Array.isArray(data.items) ? data.items : []);
    setUnread(Number(data.unread) || 0);
  }

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!me?.authenticated) return undefined;
    let cancelled = false;
    load().catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [me, t.loadError]);

  async function markOne(id) {
    const res = await fetch(`/api/auth/notifications/${id}/read`, { method: "POST" });
    if (!res.ok) {
      setError(t.loadError);
      return;
    }
    await load().catch(() => setError(t.loadError));
  }

  async function markAll() {
    const res = await fetch("/api/auth/notifications/read", { method: "POST" });
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
