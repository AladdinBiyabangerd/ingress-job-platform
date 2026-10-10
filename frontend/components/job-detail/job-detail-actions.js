"use client";

import { useState } from "react";
import { beginLogin } from "../../lib/auth-link";
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
  onRevealAnalyze,
  onRevealApplyDraft,
  formOpen = false,
  analyzeOpen = false,
  applyDraftOpen = false,
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

  function onAnalyze() {
    if (preview) {
      onRevealAnalyze?.();
      return;
    }
    if (isGuest) {
      beginLogin({ intent: "job_candidate", returnTo: model.returnTo });
      return;
    }
    onRevealAnalyze?.();
  }

  function onApplyDraft() {
    if (preview) {
      onRevealApplyDraft?.();
      return;
    }
    if (isGuest) {
      beginLogin({ intent: "job_candidate", returnTo: model.returnTo });
      return;
    }
    onRevealApplyDraft?.();
  }

  async function onPrimary() {
    if (preview) {
      if (isGuest) return;
      if (!isExternal && onRevealForm) onRevealForm();
      return;
    }
    if (isGuest) {
      beginLogin({ intent: "job_candidate", returnTo: model.returnTo });
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
        beginLogin({ intent: "job_candidate", returnTo: model.returnTo });
        return;
      }
      if (res.ok && typeof res.data?.url === "string" && res.data.url) {
        window.open(res.data.url, "_blank", "noopener,noreferrer");
        return;
      }
      const orig = await fetch(`/api/auth/jobs/${model.jobId}/original`, { cache: "no-store" });
      if (orig.status === 401 || orig.status === 403) {
        beginLogin({ intent: "job_candidate", returnTo: model.returnTo });
        return;
      }
      const data = await orig.json().catch(() => ({}));
      if (orig.ok && typeof data.url === "string" && data.url) {
        window.open(data.url, "_blank", "noopener,noreferrer");
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

  const analyzeBtn = (
    <button
      type="button"
      className="jd-btn jd-btn-outline"
      onClick={onAnalyze}
      aria-expanded={analyzeOpen || undefined}
      aria-controls="jd-analyze-panel"
    >
      <JdIcon name="book" size={16} />
      <span>{t.jdAnalyze}</span>
    </button>
  );

  const applyDraftBtn = (
    <button
      type="button"
      className="jd-btn jd-btn-outline"
      onClick={onApplyDraft}
      aria-expanded={applyDraftOpen || undefined}
      aria-controls="jd-apply-draft-panel"
    >
      <JdIcon name="pen" size={16} />
      <span>{t.jdApplyDraft}</span>
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
      {analyzeBtn}
      {applyDraftBtn}
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
