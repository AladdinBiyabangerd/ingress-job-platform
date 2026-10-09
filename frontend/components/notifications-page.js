"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { markAllNotificationsRead, markNotificationRead, refreshNotifications } from "../lib/server/refresh";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { enableBrowserPush, pushSupported } from "../lib/web-push";
import { Pager } from "./pager";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { RoleSkillParts } from "./role-skill-parts";
import { Shell } from "./shell";

const LINES = {
  application_new: "noteApplicationNew",
  application_seen: "noteApplicationSeen",
  application_rejected: "noteApplicationRejected",
  ad_approved: "noteAdApproved",
  ad_rejected: "noteAdRejected",
  ad_review: "noteAdReview",
  match_new: "noteMatchNew",
  match_near: "noteMatchNear",
  profile_nudge: "noteProfileNudge",
  coach_weekly: "noteCoachWeekly",
};

const ENGAGEMENT_KINDS = new Set(["match_new", "match_near", "profile_nudge", "coach_weekly"]);

function localePrefix(locale) {
  return locale === "en" || locale === "ru" ? `/${locale}` : "";
}

function resolveHref(locale, href) {
  if (typeof href !== "string" || !href.startsWith("/")) return "";
  if (href.startsWith("/en/") || href.startsWith("/ru/")) return href;
  return `${localePrefix(locale)}${href}`;
}

function destination(locale, item) {
  const cta = item?.payload?.cta_href;
  const resolved = resolveHref(locale, cta);
  if (resolved) return resolved;
  if (item.kind === "match_new" || item.kind === "match_near") {
    if (item.job_id) return hrefFor(locale, { jobId: item.job_id });
    return hrefFor(locale, { mode: "recommendations" });
  }
  if (item.kind === "profile_nudge") {
    return hrefFor(locale, { mode: "profileReview" });
  }
  if (item.kind === "coach_weekly") {
    return hrefFor(locale, { mode: "insights" });
  }
  if (item.kind === "application_seen" || item.kind === "application_rejected") {
    return hrefFor(locale, { mode: "applications" });
  }
  if (item.kind === "application_new" || item.kind === "ad_approved" || item.kind === "ad_rejected" || item.kind === "ad_review") {
    return hrefFor(locale, { mode: "post" });
  }
  return hrefFor(locale);
}

function secondaryHref(locale, item) {
  const payload = item?.payload || {};
  const secondary = payload.cta_secondary_href;
  const resolved = resolveHref(locale, secondary);
  if (resolved) return resolved;
  const courses = Array.isArray(payload.academy_courses) ? payload.academy_courses : [];
  const first = courses[0];
  if (first && typeof first.url === "string" && first.url.startsWith("http")) {
    return first.url;
  }
  if (item.kind === "match_near" || item.kind === "coach_weekly") {
    return hrefFor(locale, { mode: "insights" });
  }
  return "";
}

function headline(t, item) {
  const key = LINES[item.kind];
  const aiTitle = typeof item?.payload?.ai_title === "string" ? item.payload.ai_title.trim() : "";
  if (aiTitle) return aiTitle;
  if (key && typeof t[key] === "function") {
    return t[key](item.job_title || "");
  }
  return item.job_title || "";
}

function bodyText(item) {
  const aiBody = typeof item?.payload?.ai_body === "string" ? item.payload.ai_body.trim() : "";
  return aiBody;
}

function scorePct(payload) {
  const score = payload?.score;
  if (typeof score !== "number" || Number.isNaN(score)) return null;
  return Math.round(score * 100);
}

function RoadmapBlock({ t, locale, roadmap, learningRoadmap }) {
  const rich = learningRoadmap && typeof learningRoadmap === "object" ? learningRoadmap : null;
  const heroTitle = String(rich?.hero?.title || "").trim();
  const list = Array.isArray(roadmap) ? roadmap : [];
  if (!heroTitle && list.length === 0) return null;
  return (
    <div className="notice-roadmap">
      <p className="hint notice-roadmap-title">{t.noticeRoadmapTitle}</p>
      {heroTitle ? (
        <p className="notice-roadmap-hero">
          <strong className="notice-roadmap-hero-title">{heroTitle}</strong>
          {rich?.hero?.lede ? <span className="hint"> — {String(rich.hero.lede)}</span> : null}
        </p>
      ) : null}
      {list.length ? (
        <ul className="notice-roadmap-list">
          {list.slice(0, 3).map((entry, index) => {
            const skill = String(entry?.skill || "").trim();
            const steps = Array.isArray(entry?.steps) ? entry.steps.filter(Boolean) : [];
            return (
              <li key={skill || `roadmap-${index}`}>
                {skill ? <strong>{skill}</strong> : null}
                {entry?.coming_soon ? (
                  <span className="hint"> — {t.noticeComingSoon}</span>
                ) : null}
                {steps.length ? (
                  <ol>
                    {steps.slice(0, 3).map((step) => (
                      <li key={String(step)}>{String(step)}</li>
                    ))}
                  </ol>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      <a className="btn small" href={hrefFor(locale, { mode: "insightsRoadmap" })}>
        {t.roadmapOpenFull}
      </a>
    </div>
  );
}

function EngagementCard({ t, locale, item, onMark }) {
  const payload = item?.payload && typeof item.payload === "object" ? item.payload : {};
  const primary = destination(locale, item);
  const secondary = secondaryHref(locale, item);
  const title = headline(t, item);
  const body = bodyText(item);
  const pct = scorePct(payload);
  const externalSecondary = secondary.startsWith("http");

  return (
    <article className={item.read ? "notice notice-rich" : "notice notice-rich unread"}>
      <div className="notice-rich-head">
        {pct !== null ? <span className="notice-score">{pct}%</span> : null}
        <div className="notice-rich-copy">
          <a href={primary}>{title}</a>
          {body ? <p className="hint notice-body">{body}</p> : null}
        </div>
      </div>
      <RoleSkillParts t={t} have={payload.have} missing={payload.missing || payload.must_learn} />
      <RoadmapBlock
        t={t}
        locale={locale}
        roadmap={payload.roadmap}
        learningRoadmap={payload.learning_roadmap}
      />
      <div className="notice-actions">
        <a className="btn small ink" href={primary}>
          {item.kind === "profile_nudge"
            ? t.noticeCtaProfile
            : item.kind === "coach_weekly"
              ? t.noticeCtaInsights
              : t.noticeCtaOpen}
        </a>
        {secondary && secondary !== primary ? (
          <a
            className="btn small"
            href={secondary}
            {...(externalSecondary ? { target: "_blank", rel: "noreferrer" } : {})}
          >
            {externalSecondary ? t.noticeCtaLearn : t.noticeCtaInsights}
          </a>
        ) : null}
        {item.read ? null : (
          <button type="button" className="text-btn" onClick={() => onMark(item.id)}>
            {t.markRead}
          </button>
        )}
      </div>
    </article>
  );
}

function SimpleCard({ t, locale, item, onMark }) {
  const key = LINES[item.kind];
  const line = headline(t, item) || (key && typeof t[key] === "function" ? t[key](item.job_title || "") : item.job_title);
  return (
    <article className={item.read ? "notice" : "notice unread"}>
      <a href={destination(locale, item)}>{line}</a>
      {item.reason ? (
        <p className="notice-reason">
          {t.rejectReason}: {item.reason}
        </p>
      ) : null}
      {item.read ? null : (
        <button type="button" className="text-btn" onClick={() => onMark(item.id)}>
          {t.markRead}
        </button>
      )}
    </article>
  );
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
  const [pushSubActive, setPushSubActive] = useState(null);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushNote, setPushNote] = useState("");
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

  useEffect(() => {
    if (!me?.authenticated || !pushSupported()) {
      setPushSubActive(false);
      return undefined;
    }
    let cancelled = false;
    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => {
        if (!cancelled) setPushSubActive(Boolean(sub));
      })
      .catch(() => {
        if (!cancelled) setPushSubActive(false);
      });
    return () => {
      cancelled = true;
    };
  }, [me]);

  async function onEnablePush() {
    setPushBusy(true);
    setPushNote("");
    try {
      const result = await enableBrowserPush();
      if (!result.ok) {
        if (result.reason === "vapid") setPushNote(t.emailSettingsPushVapid);
        else if (result.reason === "auth") setPushNote(t.emailSettingsPushAuth);
        else if (result.reason === "upstream") setPushNote(t.emailSettingsPushUpstream);
        else if (result.reason === "denied" || result.reason === "permission") {
          setPushNote(t.emailSettingsPushDenied);
        } else if (result.reason === "unsupported") {
          setPushNote(t.emailSettingsPushUnsupported);
        } else {
          setPushNote(t.emailSettingsPushError);
        }
        return;
      }
      setPushSubActive(true);
      setPushNote(t.notificationsPushCtaDone);
    } catch {
      setPushNote(t.emailSettingsPushError);
    } finally {
      setPushBusy(false);
    }
  }

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
      {me === undefined ? null : !signedIn ? (
        <div className="h2-candidate">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.notificationsTitle}
          />
          <div className="h2-empty h2-gate">
            <p>{t.notificationsGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "notifications" })} />
          </div>
        </div>
      ) : (
        <div className="h2-candidate">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.notificationsTitle}
            count={unread > 0 ? unread : undefined}
            actions={
              unread > 0 ? (
                <button type="button" className="text-btn" onClick={markAll}>
                  {t.markAllRead}
                </button>
              ) : null
            }
          />
          {error ? <p className="note">{error}</p> : null}
          {pushSupported() && pushSubActive === false ? (
            <div className="notice-push-cta">
              <p>{t.notificationsPushCta}</p>
              <div className="notice-push-cta-actions">
                <button type="button" className="btn primary" disabled={pushBusy} onClick={onEnablePush}>
                  {t.notificationsPushCtaBtn}
                </button>
                <a className="text-btn" href={hrefFor(locale, { mode: "emailSettings" })}>
                  {t.notificationsPushCtaSettings}
                </a>
              </div>
              {pushNote ? <p className="note">{pushNote}</p> : null}
            </div>
          ) : null}
          {pushSubActive && pushNote ? <p className="note">{pushNote}</p> : null}
          {items.length === 0 ? (
            <div className="h2-empty">
              <p>{t.notificationsEmpty}</p>
            </div>
          ) : (
            <div className="notice-list h2-notice-list">
              {pageItems.map((item) =>
                ENGAGEMENT_KINDS.has(item.kind) ? (
                  <EngagementCard key={item.id} t={t} locale={locale} item={item} onMark={markOne} />
                ) : (
                  <SimpleCard key={item.id} t={t} locale={locale} item={item} onMark={markOne} />
                ),
              )}
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
        </div>
      )}
    </Shell>
  );
}
