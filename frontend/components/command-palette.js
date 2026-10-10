"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { lockBodyScroll, trapTab } from "../lib/focus-trap";
import { recommendationsEnabled, roadmapEnabled } from "../lib/product-features";
import { canPostJobs, isStaff } from "../lib/roles";

function isModK(event) {
  return (event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "k";
}

function buildItems(locale, me, t) {
  const items = [
    { id: "browse", label: t.browse, href: hrefFor(locale), group: "nav" },
    { id: "companies", label: t.navCompanies, href: hrefFor(locale, { mode: "companies" }), group: "nav" },
    { id: "trends", label: t.navTrends, href: hrefFor(locale, { mode: "trends" }), group: "nav" },
  ];
  if (canPostJobs(me)) {
    items.push({ id: "post", label: t.post, href: hrefFor(locale, { mode: "post" }), group: "nav" });
  }
  if (isStaff(me)) {
    items.push({ id: "admin", label: t.admin, href: hrefFor(locale, { mode: "admin" }), group: "nav" });
  }
  if (!me?.authenticated) return items;

  if (me.employer || me.candidate || me.staff) {
    items.push({ id: "profile", label: t.profileOpen, href: hrefFor(locale, { mode: "profile" }), group: "account" });
  }
  if (me.candidate || me.staff) {
    items.push(
      { id: "profileReview", label: t.profileReviewOpen, href: hrefFor(locale, { mode: "profileReview" }), group: "account" },
    );
    if (recommendationsEnabled()) {
      items.push({
        id: "recommendations",
        label: t.recommendationsOpen,
        href: hrefFor(locale, { mode: "recommendations" }),
        group: "account",
      });
    }
    if (roadmapEnabled()) {
      items.push({
        id: "roadmap",
        label: t.roadmapTitle,
        href: hrefFor(locale, { mode: "insightsRoadmap" }),
        group: "account",
      });
    }
    items.push(
      { id: "emailSettings", label: t.emailSettingsOpen, href: hrefFor(locale, { mode: "emailSettings" }), group: "account" },
      { id: "applications", label: t.myApplications, href: hrefFor(locale, { mode: "applications" }), group: "account" },
    );
  }
  items.push({ id: "saved", label: t.savedJobs, href: hrefFor(locale, { mode: "saved" }), group: "account" });
  items.push({ id: "notifications", label: t.notifications, href: hrefFor(locale, { mode: "notifications" }), group: "account" });
  if (me.employer || me.staff) {
    items.push({ id: "talent", label: t.talentTitle, href: hrefFor(locale, { mode: "talent" }), group: "account" });
    items.push({ id: "company", label: t.companyTitle, href: hrefFor(locale, { mode: "company" }), group: "account" });
  }
  return items;
}

export function CommandPalette({ locale, me, open, onOpenChange }) {
  const t = text(locale);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const panelRef = useRef(null);

  const items = useMemo(() => buildItems(locale, me, t), [locale, me, t]);
  const q = query.trim().toLowerCase();

  const filtered = useMemo(() => {
    if (!q) return items;
    return items.filter((item) => item.label.toLowerCase().includes(q));
  }, [items, q]);

  const jobSearchHref = useMemo(() => {
    if (!q) return null;
    const base = hrefFor(locale);
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}q=${encodeURIComponent(query.trim())}`;
  }, [locale, q, query]);

  const rows = useMemo(() => {
    const list = [...filtered];
    if (jobSearchHref) {
      list.unshift({ id: "job-q", label: `${t.cmdKJobs}: “${query.trim()}”`, href: jobSearchHref, group: "search" });
    }
    return list;
  }, [filtered, jobSearchHref, query, t.cmdKJobs]);

  const close = useCallback(() => {
    onOpenChange(false);
    setQuery("");
    setActive(0);
  }, [onOpenChange]);

  useEffect(() => {
    if (!open) return undefined;
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    const unlock = lockBodyScroll();
    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      trapTab(event, panelRef.current);
    }
    document.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(id);
      document.removeEventListener("keydown", onKey);
      unlock();
    };
  }, [open, close]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  if (!open) return null;

  function go(href) {
    close();
    window.location.href = href;
  }

  function onKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => Math.min(i + 1, Math.max(rows.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && rows[active]) {
      event.preventDefault();
      go(rows[active].href);
    }
  }

  return (
    <div className="cmdk-root" role="presentation">
      <button type="button" className="cmdk-backdrop" aria-label={t.menuClose} onClick={close} />
      <div
        className="cmdk-panel"
        role="dialog"
        aria-modal="true"
        aria-label={t.cmdKOpen}
        ref={panelRef}
      >
        <input
          ref={inputRef}
          className="cmdk-input"
          type="search"
          value={query}
          placeholder={t.cmdKPlaceholder}
          aria-label={t.cmdKOpen}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <ul className="cmdk-list" role="listbox">
          {rows.length === 0 ? (
            <li className="cmdk-empty">{t.cmdKEmpty}</li>
          ) : (
            rows.map((row, index) => (
              <li key={row.id} role="option" aria-selected={index === active}>
                <button
                  type="button"
                  className={`cmdk-item${index === active ? " on" : ""}`}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => go(row.href)}
                >
                  {row.label}
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}

export function useCommandPaletteHotkey(onOpen) {
  useEffect(() => {
    function onKey(event) {
      if (!isModK(event)) return;
      const tag = event.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || event.target?.isContentEditable) {
        if (event.target?.closest?.(".cmdk-panel")) return;
      }
      event.preventDefault();
      onOpen();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onOpen]);
}
