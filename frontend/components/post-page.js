"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { Cabinet } from "./cabinet";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

export function PostPage({ locale }) {
  const t = text(locale);
  const [me, setMe] = useState(undefined);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        if (data?.needs_company_profile) {
          window.location.href = hrefFor(locale, { mode: "company" });
          return;
        }
        setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  const canPost = Boolean(me?.authenticated && (me.employer || me.staff) && !me.needs_company_profile);

  return (
    <Shell locale={locale} mode="post">
      {canPost ? (
        <Cabinet locale={locale} me={me} />
      ) : (
        <section className="empty">
          <h1>{t.postTitle}</h1>
          <p className="lede">{t.postBody}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "post" })} />
        </section>
      )}
    </Shell>
  );
}
