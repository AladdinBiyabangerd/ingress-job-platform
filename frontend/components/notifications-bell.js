"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";

export function NotificationsBell({ locale }) {
  const t = text(locale);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/notifications", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : { unread: 0 }))
      .then((data) => {
        if (!cancelled) setUnread(Number(data.unread) || 0);
      })
      .catch(() => {
        if (!cancelled) setUnread(0);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const label = unread > 0 ? t.notificationsUnread(unread) : t.notifications;

  return (
    <a className="bell" href={hrefFor(locale, { mode: "notifications" })} aria-label={label} title={label}>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 3.5a5 5 0 0 0-5 5v2.2c0 .7-.2 1.3-.6 1.9L5 14.8h14l-1.4-2.2a3.4 3.4 0 0 1-.6-1.9V8.5a5 5 0 0 0-5-5Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M10 17.5a2 2 0 0 0 4 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      {unread > 0 ? <span className="bell-count">{unread > 99 ? "99+" : unread}</span> : null}
    </a>
  );
}
