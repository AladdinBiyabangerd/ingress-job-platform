"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { Admin } from "./admin";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

export function AdminPage({ locale }) {
  const t = text(locale);
  const [me, setMe] = useState(undefined);

  useEffect(() => {
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
  }, []);

  const isStaff = Boolean(me?.authenticated && me.staff);

  return (
    <Shell locale={locale} mode="admin">
      {me === undefined ? null : isStaff ? (
        <Admin locale={locale} />
      ) : (
        <section className="empty">
          <h1>{t.adminTitle}</h1>
          <p className="lede">{t.adminGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "admin" })} />
        </section>
      )}
    </Shell>
  );
}
