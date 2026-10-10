"use client";

import { useState } from "react";
import { loginHref } from "../../lib/auth-link";
import { text } from "../../lib/copy";
import { applyToJob } from "../../lib/server/refresh";
import { SaveJobButton } from "../save-job-button";
import { JdIcon } from "./jd-icons";

function primaryLabel(t, model) {
  if (model.authState === "guest") return t.signInToApply;
  if (model.listingType === "external") return t.openOriginalListing;
  return t.apply;
}

export function JobDetailActions({
  locale,
  model,
  layout = "desktop",
  onRevealForm,
  formOpen = false,
  preview = false,
  className = "",
}) {
  const t = text(locale);
  const [shareNote, setShareNote] = useState("");
  const [busy, setBusy] = useState(false);
  const label = primaryLabel(t, model);
  const isGuest = model.authState === "guest";
  const isExternal = model.listingType === "external";
  const primaryClass =
    isGuest && !isExternal ? "jd-btn jd-btn-soft" : "jd-btn jd-btn-primary";

  async function onPrimary() {
    if (preview) {
      if (isGuest) return;
      if (!isExternal && onRevealForm) onRevealForm();
      return;
    }
    if (isGuest) {
      window.location.href = loginHref({ intent: "job_candidate", returnTo: model.returnTo });
      return;
    }
    if (!isExternal) {
      onRevealForm?.();
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      const res = await applyToJob(model.jobId);
      if (res.status === 401 || res.status === 403) {
        window.location.href = loginHref({ intent: "job_candidate", returnTo: model.returnTo });
        return;
      }
      if (res.ok && typeof res.data?.url === "string" && res.data.url) {
        window.location.href = res.data.url;
        return;
      }
      const orig = await fetch(`/api/auth/jobs/${model.jobId}/original`, { cache: "no-store" });
      if (orig.status === 401 || orig.status === 403) {
        window.location.href = loginHref({ intent: "job_candidate", returnTo: model.returnTo });
        return;
      }
      const data = await orig.json().catch(() => ({}));
      if (orig.ok && typeof data.url === "string" && data.url) {
        window.location.href = data.url;
      }
    } finally {
      setBusy(false);
    }
  }

  async function onShare() {
    const url =
      typeof window !== "undefined"
        ? model.preview
          ? window.location.href
          : `${window.location.origin}${model.returnTo}`
        : model.returnTo;
    const title = model.title || "Ingress Job";
    try {
      if (typeof navigator !== "undefined" && navigator.share) {
        await navigator.share({ title, url });
        return;
      }
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        setShareNote(t.jdShareCopied);
        window.setTimeout(() => setShareNote(""), 2000);
      }
    } catch {
      /* user cancelled share */
    }
  }

  const primary = (
    <button
      type="button"
      className={primaryClass}
      onClick={onPrimary}
      disabled={busy || (formOpen && !isExternal && !isGuest)}
      aria-expanded={!isExternal && !isGuest ? formOpen : undefined}
    >
      {label}
    </button>
  );

  const secondary = (
    <>
      {preview ? (
        <button type="button" className="jd-btn jd-btn-outline">
          <JdIcon name="star" size={16} />
          <span>{t.jdSave}</span>
        </button>
      ) : (
        <SaveJobButton
          locale={locale}
          jobId={model.jobId}
          returnTo={model.returnTo}
          showLabel
          className="jd-btn jd-btn-outline jd-save"
        />
      )}
      <button type="button" className="jd-btn jd-btn-outline" onClick={onShare}>
        <JdIcon name="share" size={16} />
        <span>{t.jdShare}</span>
      </button>
    </>
  );

  if (layout === "sidebar") {
    return (
      <div className={`jd-actions jd-actions-sidebar ${className}`.trim()}>
        {primary}
        {shareNote ? (
          <p className="jd-share-note" role="status">
            {shareNote}
          </p>
        ) : null}
      </div>
    );
  }

  if (layout === "mobile" || layout === "sticky") {
    return (
      <div className={`jd-actions jd-actions-${layout} ${className}`.trim()}>
        {primary}
        <div className="jd-actions-row">{secondary}</div>
        {shareNote ? (
          <p className="jd-share-note" role="status">
            {shareNote}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className={`jd-actions jd-actions-desktop ${className}`.trim()}>
      {secondary}
      {primary}
      {shareNote ? (
        <p className="jd-share-note jd-share-note-abs" role="status">
          {shareNote}
        </p>
      ) : null}
    </div>
  );
}
