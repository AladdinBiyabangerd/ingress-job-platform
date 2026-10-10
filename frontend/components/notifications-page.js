"use client";

import { useEffect, useMemo, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { recommendationsEnabled, roadmapEnabled } from "../lib/product-features";
import { markAllNotificationsRead, markNotificationRead, refreshNotifications } from "../lib/server/refresh";
import { publishUnreadNotifications } from "../lib/unread-document-title";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { enableBrowserPush, pushSupported } from "../lib/web-push";
import { Pager } from "./pager";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { RoleSkillParts } from "./role-skill-parts";
import { SkillPills } from "./roadmap";
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
const MATCH_KINDS = new Set(["match_new", "match_near"]);
const LEARNING_KINDS = new Set(["coach_weekly"]);
const APP_KINDS = new Set([
  "application_new",
  "application_seen",
  "application_rejected",
  "ad_approved",
  "ad_rejected",
  "ad_review",
]);

const FILTERS = [
  { id: "all", kinds: null },
  { id: "matches", kinds: MATCH_KINDS },
  { id: "learning", kinds: LEARNING_KINDS },
  { id: "profile", kinds: new Set(["profile_nudge"]) },
  { id: "apps", kinds: APP_KINDS },
];

function visibleFilters() {
  if (roadmapEnabled()) return FILTERS;
  return FILTERS.filter((filter) => filter.id !== "learning");
}

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
  if (resolved) {
    if (!roadmapEnabled() && resolved.includes("/me/insights")) return hrefFor(locale);
    if (!recommendationsEnabled() && resolved.includes("/me/recommendations")) {
      if (item.job_id) return hrefFor(locale, { jobId: item.job_id });
      return hrefFor(locale);
    }
    return resolved;
  }
  if (item.kind === "match_new" || item.kind === "match_near") {
    if (item.job_id) return hrefFor(locale, { jobId: item.job_id });
    return recommendationsEnabled()
      ? hrefFor(locale, { mode: "recommendations" })
      : hrefFor(locale);
  }
  if (item.kind === "profile_nudge") {
    return hrefFor(locale, { mode: "profileReview" });
  }
  if (item.kind === "coach_weekly") {
    return roadmapEnabled() ? hrefFor(locale, { mode: "insightsRoadmap" }) : hrefFor(locale);
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
  if (resolved) {
    if (!roadmapEnabled() && resolved.includes("/me/insights")) return "";
    if (!recommendationsEnabled() && resolved.includes("/me/recommendations")) return "";
    return resolved;
  }
  const courses = Array.isArray(payload.academy_courses) ? payload.academy_courses : [];
  const first = courses[0];
  if (first && typeof first.url === "string" && first.url.startsWith("http")) {
    return first.url;
  }
  if (roadmapEnabled() && (item.kind === "match_near" || item.kind === "coach_weekly")) {
    return hrefFor(locale, { mode: "insightsRoadmap" });
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

function payloadOf(item) {
  return item?.payload && typeof item.payload === "object" ? item.payload : {};
}

function hasGrowth(item) {
  const payload = payloadOf(item);
  const rich = payload.learning_roadmap;
  const hero = rich && typeof rich === "object" ? String(rich?.hero?.title || "").trim() : "";
  const roadmap = Array.isArray(payload.roadmap) ? payload.roadmap : [];
  const missing = payload.missing || payload.must_learn;
  const have = payload.have;
  return Boolean(hero || roadmap.length || (Array.isArray(missing) && missing.length) || (Array.isArray(have) && have.length));
}

function kindLabel(t, kind) {
  if (MATCH_KINDS.has(kind)) return t.notificationsFilterMatches;
  if (kind === "coach_weekly") return t.notificationsFilterLearning;
  if (kind === "profile_nudge") return t.notificationsFilterProfile;
  if (APP_KINDS.has(kind)) return t.notificationsFilterApps;
  return t.notificationsFilterAll;
}

function filterLabel(t, id) {
  if (id === "matches") return t.notificationsFilterMatches;
  if (id === "learning") return t.notificationsFilterLearning;
  if (id === "profile") return t.notificationsFilterProfile;
  if (id === "apps") return t.notificationsFilterApps;
  return t.notificationsFilterAll;
}

function countForFilter(items, filter) {
  if (!filter.kinds) return items.length;
  return items.filter((item) => filter.kinds.has(item.kind)).length;
}

function unreadForFilter(items, filter) {
  const list = filter.kinds ? items.filter((item) => filter.kinds.has(item.kind)) : items;
  return list.filter((item) => !item.read).length;
}

function RailMatchRing({ pct }) {
  if (pct === null) return null;
  const r = 18;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.min(100, Math.max(0, pct)) / 100);
  return (
    <div className="notes-c-rail-ring" aria-label={`${pct}%`}>
      <svg viewBox="0 0 48 48" width="52" height="52" aria-hidden="true">
        <circle cx="24" cy="24" r={r} fill="none" stroke="rgb(0 31 255 / 12%)" strokeWidth="5" />
        <circle
          className="notes-c-rail-ring-arc"
          cx="24"
          cy="24"
          r={r}
          fill="none"
          stroke="var(--brand)"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          transform="rotate(-90 24 24)"
        />
      </svg>
      <span className="notes-c-rail-ring-pct">{pct}%</span>
    </div>
  );
}

function GrowthRail({ t, locale, item, onBack }) {
  if (!item) {
    return (
      <aside className="notes-c-rail" aria-label={t.notificationsGrowthTitle}>
        {onBack ? (
          <button type="button" className="notes-c-rail-back text-btn" onClick={onBack}>
            {t.applicationsBackToList}
          </button>
        ) : null}
        <div className="notes-c-rail-empty">
          <p className="hint">{t.notificationsGrowthEmpty}</p>
        </div>
      </aside>
    );
  }

  const payload = payloadOf(item);
  const rich = payload.learning_roadmap && typeof payload.learning_roadmap === "object" ? payload.learning_roadmap : null;
  const hero = rich?.hero && typeof rich.hero === "object" ? rich.hero : null;
  const heroTitle = String(hero?.title || "").trim();
  const heroLede = String(hero?.lede || hero?.motivation || "").trim();
  const weekSkill = String(hero?.skill || payload.roadmap?.[0]?.skill || "").trim();
  const weekItems = Array.isArray(rich?.this_week?.items) ? rich.this_week.items : [];
  const pathSteps = Array.isArray(rich?.academy_path?.steps) ? rich.academy_path.steps : [];
  const roadmap = Array.isArray(payload.roadmap) ? payload.roadmap : [];
  const haveSkills = hero?.have || payload.have;
  const missingSkills = hero?.missing || payload.missing || payload.must_learn;
  const pct = scorePct(payload);
  const courses = Array.isArray(payload.academy_courses)
    ? payload.academy_courses
    : Array.isArray(rich?.academy_courses)
      ? rich.academy_courses
      : [];
  const primary = destination(locale, item);
  const secondary = secondaryHref(locale, item);
  const externalSecondary = secondary.startsWith("http");
  const showGrowth =
    roadmapEnabled()
    && Boolean(heroTitle || roadmap.length || weekSkill || weekItems.length || pathSteps.length);

  const upcoming = (pathSteps.length
    ? pathSteps.slice(0, 5).map((step, index) => {
        const title = String(step?.title || "").trim();
        if (!title) return null;
        return { key: `${step?.n || index}-${title}`, title, soon: false };
      })
    : roadmap.slice(0, 5).map((entry, index) => {
        const skill = String(entry?.skill || "").trim();
        if (!skill) return null;
        return {
          key: skill || `rail-${index}`,
          title: skill,
          soon: Boolean(entry?.coming_soon),
        };
      })
  ).filter(Boolean);

  const weekKey = weekSkill.toLowerCase();
  const journeyTail = upcoming
    .filter((step) => !weekKey || step.title.toLowerCase() !== weekKey)
    .slice(0, 4);
  const hasJourney = Boolean(weekSkill || weekItems.length || journeyTail.length);

  return (
    <aside className="notes-c-rail" aria-label={t.notificationsGrowthTitle}>
      {onBack ? (
        <button type="button" className="notes-c-rail-back text-btn" onClick={onBack}>
          {t.applicationsBackToList}
        </button>
      ) : null}
      {!showGrowth ? (
        <div className="notes-c-rail-empty">
          <p className="hint">{t.notificationsGrowthEmpty}</p>
          <a className="btn small ink" href={primary}>
            {item.kind === "profile_nudge"
              ? t.noticeCtaProfile
              : item.kind === "coach_weekly"
                ? t.noticeCtaInsights
                : t.noticeCtaOpen}
          </a>
        </div>
      ) : (
        <div className="notes-c-rail-card">
          <div className="notes-c-rail-hero">
            <div className="notes-c-rail-hero-top">
              <div className="notes-c-rail-hero-copy">
                <p className="notes-c-rail-kicker">{t.roadmapTitle}</p>
                {heroTitle ? <h2 className="notes-c-rail-title">{heroTitle}</h2> : null}
                {heroLede ? <p className="hint notes-c-rail-lede">{heroLede}</p> : null}
              </div>
              <RailMatchRing pct={pct} />
            </div>
            {weekSkill ? (
              <p className="notes-c-rail-focus">
                <span className="notes-c-rail-focus-dot" aria-hidden="true" />
                <span className="notes-c-rail-focus-label">{t.roadmapThisWeek}</span>
                <span className="notes-c-rail-focus-skill">{weekSkill}</span>
              </p>
            ) : null}
            <SkillPills t={t} have={haveSkills} missing={missingSkills} limit={6} />
          </div>

          {hasJourney ? (
            <ol className="notes-c-rail-journey" aria-label={t.roadmapAcademyPath}>
              {weekSkill || weekItems.length ? (
                <li className="notes-c-rail-step is-current">
                  <span className="notes-c-rail-node" aria-hidden="true" />
                  <div className="notes-c-rail-step-body">
                    <p className="notes-c-rail-step-title">
                      {t.roadmapThisWeek}
                      {weekSkill ? <span className="notes-c-rail-step-skill"> · {weekSkill}</span> : null}
                    </p>
                    {weekItems.length ? (
                      <ul className="roadmap-check-list notes-c-rail-checks">
                        {weekItems.slice(0, 3).map((entry, index) => {
                          const textLine = String(entry?.text || "").trim();
                          if (!textLine) return null;
                          return (
                            <li key={`week-${index}`}>
                              <span className="roadmap-check" aria-hidden="true" />
                              <span className="roadmap-check-text">{textLine}</span>
                            </li>
                          );
                        })}
                      </ul>
                    ) : null}
                  </div>
                </li>
              ) : null}
              {journeyTail.map((step, index) => (
                <li key={step.key} className="notes-c-rail-step">
                  <span className="notes-c-rail-node" aria-hidden="true" />
                  <div className="notes-c-rail-step-body">
                    <p className="notes-c-rail-step-title">
                      <span className="notes-c-rail-step-n">{index + (weekSkill || weekItems.length ? 2 : 1)}</span>
                      {step.title}
                      {step.soon ? <span className="hint"> — {t.noticeComingSoon}</span> : null}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          ) : null}

          {courses[0]?.url ? (
            <a className="notes-c-rail-course" href={courses[0].url} target="_blank" rel="noreferrer">
              <span className="notes-c-rail-course-label">{t.noticeCtaLearn}</span>
              <span className="notes-c-rail-course-title">{courses[0].title || t.noticeCtaLearn}</span>
            </a>
          ) : null}

          <div className="notes-c-rail-actions">
            {roadmapEnabled() ? (
              <a className="btn small ink" href={hrefFor(locale, { mode: "insightsRoadmap" })}>
                {t.roadmapOpenFull}
              </a>
            ) : null}
            {secondary && secondary !== primary ? (
              <a
                className="btn small"
                href={secondary}
                {...(externalSecondary ? { target: "_blank", rel: "noreferrer" } : {})}
              >
                {externalSecondary ? t.noticeCtaLearn : t.noticeCtaInsights}
              </a>
            ) : null}
          </div>
        </div>
      )}
    </aside>
  );
}

function FeedCard({ t, locale, item, selected, onSelect, onMark }) {
  const payload = payloadOf(item);
  const primary = destination(locale, item);
  const secondary = secondaryHref(locale, item);
  const title = headline(t, item);
  const body = bodyText(item);
  const pct = scorePct(payload);
  const rich = ENGAGEMENT_KINDS.has(item.kind);
  const externalSecondary = secondary.startsWith("http");
  const classes = [
    "notes-c-card",
    item.read ? "" : "is-unread",
    selected ? "is-selected" : "",
    rich ? "is-rich" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <article className={classes}>
      <button type="button" className="notes-c-card-hit" onClick={() => onSelect(item.id)} aria-pressed={selected}>
        <span className="notes-c-card-meta">
          <span className="notes-c-card-kind">{kindLabel(t, item.kind)}</span>
          {pct !== null ? <span className="notice-score">{pct}%</span> : null}
        </span>
        <span className="notes-c-card-title">{title}</span>
        {body ? <span className="hint notes-c-card-body">{body}</span> : null}
        {item.reason ? (
          <span className="notice-reason">
            {t.rejectReason}: {item.reason}
          </span>
        ) : null}
        {rich ? (
          <RoleSkillParts t={t} have={payload.have} missing={payload.missing || payload.must_learn} limit={5} />
        ) : null}
      </button>
      <div className="notes-c-card-actions">
        <a className="btn small ink" href={primary}>
          {item.kind === "profile_nudge"
            ? t.noticeCtaProfile
            : item.kind === "coach_weekly"
              ? t.noticeCtaInsights
              : t.noticeCtaOpen}
        </a>
        {rich && secondary && secondary !== primary ? (
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
  const [filterId, setFilterId] = useState("all");
  const [selectedId, setSelectedId] = useState(null);
  const [mobileDetail, setMobileDetail] = useState(false);

  const filters = visibleFilters();
  const activeFilter = filters.find((f) => f.id === filterId) || filters[0];
  const filteredItems = useMemo(() => {
    let list = items;
    if (!roadmapEnabled()) {
      list = list.filter((item) => item.kind !== "coach_weekly");
    }
    if (!activeFilter.kinds) return list;
    return list.filter((item) => activeFilter.kinds.has(item.kind));
  }, [items, activeFilter]);

  const { pageItems, currentPage, totalPages, pageSize, total, goToPage, resetPage } = usePagination(
    filteredItems,
    LIST_PAGE_SIZE,
  );

  const selectedItem = useMemo(() => {
    if (selectedId == null) return null;
    return filteredItems.find((item) => item.id === selectedId) || pageItems.find((item) => item.id === selectedId) || null;
  }, [filteredItems, pageItems, selectedId]);

  useEffect(() => {
    if (!pageItems.length) {
      setSelectedId(null);
      return;
    }
    const stillVisible = pageItems.some((item) => item.id === selectedId);
    if (stillVisible) return;
    const prefer = pageItems.find((item) => hasGrowth(item)) || pageItems[0];
    setSelectedId(prefer?.id ?? null);
  }, [pageItems, selectedId]);

  async function load() {
    const data = await refreshNotifications();
    setItems(data.items);
    setUnread(data.unread);
  }

  useEffect(() => {
    publishUnreadNotifications(unread);
  }, [unread]);

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

  function onFilter(nextId) {
    setFilterId(nextId);
    resetPage();
    setMobileDetail(false);
  }

  function onSelect(id) {
    setSelectedId(id);
    setMobileDetail(true);
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

          {items.length === 0 ? (
            <div className="h2-empty">
              <p>{t.notificationsEmpty}</p>
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
            </div>
          ) : (
            <div className={["notes-c", mobileDetail ? "is-mobile-detail" : ""].filter(Boolean).join(" ")}>
              <nav className="notes-c-filters" aria-label={t.notificationsTitle}>
                <ul className="notes-c-filter-list">
                  {filters.map((filter) => {
                    const count = countForFilter(items, filter);
                    const unreadCount = unreadForFilter(items, filter);
                    const active = filter.id === filterId;
                    return (
                      <li key={filter.id}>
                        <button
                          type="button"
                          className={["notes-c-filter", active ? "is-active" : ""].filter(Boolean).join(" ")}
                          onClick={() => onFilter(filter.id)}
                          aria-pressed={active}
                        >
                          <span className="notes-c-filter-label">{filterLabel(t, filter.id)}</span>
                          <span className="notes-c-filter-count">{count}</span>
                          {unreadCount > 0 ? <span className="notes-c-filter-unread">{unreadCount}</span> : null}
                        </button>
                      </li>
                    );
                  })}
                </ul>
                {pushSupported() ? (
                  <div className="notes-c-push">
                    {pushSubActive === false ? (
                      <>
                        <p className="hint">{t.notificationsPushCta}</p>
                        <button type="button" className="btn small primary" disabled={pushBusy} onClick={onEnablePush}>
                          {t.notificationsPushCtaBtn}
                        </button>
                        <a className="text-btn" href={hrefFor(locale, { mode: "emailSettings" })}>
                          {t.notificationsPushCtaSettings}
                        </a>
                      </>
                    ) : pushSubActive ? (
                      <p className="hint">{t.emailSettingsPushSubOn}</p>
                    ) : null}
                    {pushNote ? <p className="note">{pushNote}</p> : null}
                  </div>
                ) : null}
              </nav>

              <section className="notes-c-feed" aria-label={t.notificationsTitle}>
                {filteredItems.length === 0 ? (
                  <div className="notes-c-feed-empty">
                    <p className="hint">{t.notificationsFilterEmpty}</p>
                  </div>
                ) : (
                  <>
                    <div className="notes-c-feed-scroll">
                      {pageItems.map((item) => (
                        <FeedCard
                          key={item.id}
                          t={t}
                          locale={locale}
                          item={item}
                          selected={item.id === selectedId}
                          onSelect={onSelect}
                          onMark={markOne}
                        />
                      ))}
                    </div>
                    <Pager
                      locale={locale}
                      currentPage={currentPage}
                      totalPages={totalPages}
                      total={total}
                      pageSize={pageSize}
                      onPageChange={(page) => {
                        goToPage(page);
                        setMobileDetail(false);
                      }}
                    />
                  </>
                )}
              </section>

              <GrowthRail t={t} locale={locale} item={selectedItem} onBack={() => setMobileDetail(false)} />
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
