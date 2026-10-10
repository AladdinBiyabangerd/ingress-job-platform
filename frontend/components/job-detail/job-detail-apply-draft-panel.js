"use client";

import { useEffect, useRef, useState } from "react";
import { beginLogin } from "../../lib/auth-link";
import { hrefFor, text } from "../../lib/copy";
import { LoginLink } from "../login-link";

const POLL_MS = 2500;
const POLL_MAX = 20;

function aiErrorMessage(t, code) {
  const raw = String(code || "").trim();
  if (!raw || raw === "ai_pending") return "";
  if (raw === "job_apply_draft_disabled" || raw === "ai_disabled") return t.jdApplyDraftAiOff;
  if (raw === "ai_no_key") return t.jdApplyDraftErrorNoKey;
  if (raw.includes("budget")) return t.jdApplyDraftErrorBudget;
  if (raw.includes("provider") || raw === "ai_failed") return t.jdApplyDraftErrorProvider;
  if (raw === "ai_validation_failed") return t.jdApplyDraftErrorValidation;
  return t.jdApplyDraftErrorCode(raw);
}

/**
 * Apply-message draft panel. For company_posted, parent fills the apply form via onMessage.
 * For external listings, shows the text + copy.
 */
export function JobDetailApplyDraftPanel({
  locale,
  jobId,
  returnTo,
  listingType = "external",
  open,
  preview = false,
  onMessage,
}) {
  const t = text(locale);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copyNote, setCopyNote] = useState("");
  const pollLeft = useRef(0);
  const delivered = useRef("");
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!open || preview || !jobId) return undefined;
    let cancelled = false;
    let timer = 0;
    setLoading(true);
    setError("");
    setPayload(null);
    setCopyNote("");
    pollLeft.current = POLL_MAX;
    delivered.current = "";

    async function load(refresh = false) {
      const qs = new URLSearchParams({ lang: locale || "az" });
      if (refresh) qs.set("refresh", "1");
      const res = await fetch(`/api/auth/me/jobs/${jobId}/apply-draft?${qs}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ refresh: Boolean(refresh) }),
        cache: "no-store",
      });
      if (res.status === 401 || res.status === 403) {
        beginLogin({ intent: "job_candidate", returnTo });
        return null;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error("load");
      return data;
    }

    function finish(data) {
      if (cancelled || !data) return;
      setPayload(data);
      setLoading(Boolean(data.ai_pending));
      const msg = typeof data.message === "string" ? data.message.trim() : "";
      if (msg && msg !== delivered.current) {
        delivered.current = msg;
        onMessageRef.current?.(msg);
      }
      if (data.ai_pending && pollLeft.current > 0) {
        pollLeft.current -= 1;
        timer = window.setTimeout(() => {
          load(false)
            .then(finish)
            .catch(() => {
              if (!cancelled) {
                setError(t.jdApplyDraftErrorProvider);
                setLoading(false);
              }
            });
        }, POLL_MS);
      } else if (data.ai_pending) {
        setError(t.jdApplyDraftErrorProvider);
        setLoading(false);
      }
    }

    load(false)
      .then(finish)
      .catch(() => {
        if (!cancelled) {
          setError(t.jdApplyDraftErrorProvider);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [open, preview, jobId, locale, returnTo, t.jdApplyDraftErrorProvider]);

  if (!open) return null;

  const status = payload?.status || "";
  const message = typeof payload?.message === "string" ? payload.message.trim() : "";
  const aiErr = aiErrorMessage(t, payload?.ai_error || error);
  const isExternal = listingType === "external";
  const showMessage = Boolean(message) && (isExternal || status === "ok");

  async function onCopy() {
    if (!message) return;
    try {
      await navigator.clipboard?.writeText(message);
      setCopyNote(t.jdApplyDraftCopied);
      window.setTimeout(() => setCopyNote(""), 2000);
    } catch {
      setCopyNote("");
    }
  }

  return (
    <section className="jd-apply-draft" id="jd-apply-draft-panel" aria-labelledby="jd-apply-draft-title">
      <div className="jd-apply-draft-head">
        <h2 id="jd-apply-draft-title">{t.jdApplyDraftTitle}</h2>
        {loading || payload?.ai_pending ? (
          <p className="jd-apply-draft-status" role="status">
            {t.jdApplyDraftPending}
          </p>
        ) : null}
      </div>

      {preview ? <p className="jd-apply-draft-gate">{t.jdApplyDraftPreview}</p> : null}

      {!preview && status === "needs_consent" ? (
        <div className="jd-apply-draft-gate">
          <p>{t.jdApplyDraftConsent}</p>
          <a className="jd-btn jd-btn-outline" href={hrefFor(locale, { mode: "profile" })}>
            {t.jdApplyDraftConsentCta}
          </a>
        </div>
      ) : null}

      {!preview && status === "needs_profile" ? (
        <div className="jd-apply-draft-gate">
          <p>{t.jdApplyDraftSkills}</p>
          <a className="jd-btn jd-btn-outline" href={hrefFor(locale, { mode: "profileReview" })}>
            {t.jdApplyDraftSkillsCta}
          </a>
        </div>
      ) : null}

      {!preview && !payload && !loading ? (
        <div className="jd-apply-draft-gate">
          <p>{t.jdApplyDraftGuest}</p>
          <LoginLink intent="job_candidate" returnTo={returnTo} className="btn small">
            {t.jdApplyDraftGuestCta}
          </LoginLink>
        </div>
      ) : null}

      {!preview && status === "ok" && !message && !loading && !payload?.ai_pending ? (
        <p className="jd-apply-draft-error" role="alert">
          {aiErr || t.jdApplyDraftErrorProvider}
        </p>
      ) : null}

      {!preview && aiErr && (message || payload?.ai_pending) ? (
        <p className="jd-apply-draft-note" role="status">
          {aiErr}
        </p>
      ) : null}

      {!preview && showMessage ? (
        <div className="jd-apply-draft-body">
          {isExternal ? (
            <>
              <pre className="jd-apply-draft-text">{message}</pre>
              <div className="jd-apply-draft-actions">
                <button type="button" className="btn small" onClick={onCopy}>
                  {t.jdApplyDraftCopy}
                </button>
                {copyNote ? (
                  <span className="jd-apply-draft-copied" role="status">
                    {copyNote}
                  </span>
                ) : null}
              </div>
            </>
          ) : (
            <p className="jd-apply-draft-note" role="status">
              {t.jdApplyDraftFilled}
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}
