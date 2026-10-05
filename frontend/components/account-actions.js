"use client";

import { useEffect, useState } from "react";
import { loginHref } from "../lib/auth-link";
import { applyFormFromJob } from "../lib/apply-form";
import { text } from "../lib/copy";
import { ApplicationList, appStatusLabel } from "./application-list";
import { ConsentFields, grantsFromPayload } from "./consent-fields";

const CV_OK = /\.(pdf|doc|docx)$/i;
const EMAIL_OK = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function AccountActions({ locale, jobId, returnTo, onsite, hasOriginal, form }) {
  const t = text(locale);
  const spec = onsite ? applyFormFromJob({ form: form || null }) : null;
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [answers, setAnswers] = useState({});
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [mine, setMine] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [profile, setProfile] = useState(null);
  const [phoneEdited, setPhoneEdited] = useState(false);
  const [emailEdited, setEmailEdited] = useState(false);
  const [consentPayload, setConsentPayload] = useState(null);
  const [grants, setGrants] = useState({ matching: false, emails: false, recruiter_visibility: false });

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/applications", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data && Array.isArray(data.items)) setMine(data.items);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled) setProfile(data?.candidate_profile || null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const phoneOn = Boolean(spec?.phone?.enabled);
  const emailOn = Boolean(spec?.email?.enabled);

  useEffect(() => {
    if (!profile) return;
    if (phoneOn && !phoneEdited) setPhone(profile.phone || "");
    if (emailOn && !emailEdited) setEmail(profile.email || "");
  }, [profile, phoneOn, emailOn, phoneEdited, emailEdited]);

  const showConsents = Boolean(onsite && spec?.cv?.enabled);

  useEffect(() => {
    if (!showConsents) return undefined;
    let cancelled = false;
    fetch(`/api/auth/consents?lang=${encodeURIComponent(locale)}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setConsentPayload(data);
        setGrants(grantsFromPayload(data));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [showConsents, locale]);

  const current = mine.find((item) => item.job_id === jobId);

  async function openLink(kind) {
    const res = await fetch(`/api/auth/jobs/${jobId}/${kind}`, {
      method: kind === "apply" ? "POST" : "GET",
      cache: "no-store",
    });
    if (res.status === 401 || res.status === 403) {
      window.location.href = loginHref({ intent: "job_candidate", returnTo });
      return;
    }
    const data = await res.json().catch(() => ({}));
    if (res.ok && typeof data.url === "string" && data.url) {
      window.location.href = data.url;
      return;
    }
    setOpen(true);
  }

  function validate() {
    if (spec.message.enabled && spec.message.required && !message.trim()) return t.applyRequired;
    if (spec.message.enabled && message.length > 2000) return t.applyRequired;
    if (spec.phone.enabled) {
      const digits = phone.replace(/\D/g, "");
      if (spec.phone.required && !phone.trim()) return t.applyFieldRequired;
      if (phone.trim() && (digits.length < 5 || phone.trim().length > 40)) return t.applyPhoneInvalid;
    }
    if (spec.email.enabled) {
      if (spec.email.required && !email.trim()) return t.applyFieldRequired;
      if (email.trim() && !EMAIL_OK.test(email.trim())) return t.applyEmailInvalid;
    }
    for (const question of spec.questions) {
      const answer = (answers[question.id] || "").trim();
      if (question.required && !answer) return t.applyFieldRequired;
      if (answer.length > 2000) return t.applyFieldRequired;
    }
    if (spec.cv.enabled && spec.cv.required && !file) return t.applyCvRequired;
    if (file && (file.size > 5 * 1024 * 1024 || !CV_OK.test(file.name || ""))) return t.applyCvRequired;
    return "";
  }

  async function sendApplication(event) {
    event.preventDefault();
    setError("");
    setNote("");
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    const body = new FormData();
    if (spec.message.enabled) body.set("message", message);
    if (spec.phone.enabled) body.set("phone", phone);
    if (spec.email.enabled) body.set("email", email);
    if (spec.questions.length) {
      body.set(
        "answers",
        JSON.stringify(spec.questions.map((question) => ({ id: question.id, answer: answers[question.id] || "" }))),
      );
    }
    if (spec.cv.enabled && file) body.set("cv", file);
    const res = await fetch(`/api/auth/jobs/${jobId}/apply`, { method: "POST", body });
    setBusy(false);
    if (res.status === 401 || res.status === 403) {
      window.location.href = loginHref({ intent: "job_candidate", returnTo });
      return;
    }
    if (res.status === 409) {
      setError(t.applyDuplicate);
      return;
    }
    if (!res.ok) {
      setError(res.status === 422 ? t.applyFieldRequired : t.applyError);
      return;
    }
    if (showConsents && consentPayload) {
      await fetch(`/api/auth/consents?lang=${encodeURIComponent(locale)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(grants),
      }).catch(() => {});
    }
    setMessage("");
    setPhoneEdited(false);
    setEmailEdited(false);
    setPhone("");
    setEmail("");
    setAnswers({});
    setFile(null);
    setNote(t.applySent);
    setReloadKey((value) => value + 1);
  }

  return (
    <>
      {onsite && current ? (
        <p className="note" role="status">
          {t.applySent} {appStatusLabel(t, current.status)}
          {current.reason ? `. ${t.rejectReason}: ${current.reason}` : ""}
        </p>
      ) : null}
      {onsite && !current ? (
        <form className="form-card apply-box" onSubmit={sendApplication}>
          <h2>{t.apply}</h2>
          {error ? <p className="note">{error}</p> : null}
          {note ? <p className="note">{note}</p> : null}
          {spec.message.enabled ? (
            <label>
              {t.applyMessage}
              {spec.message.required ? null : <span className="hint">{t.adOptional}</span>}
              <textarea value={message} maxLength={2000} required={spec.message.required} rows={4} onChange={(event) => setMessage(event.target.value)} />
            </label>
          ) : null}
          {spec.phone.enabled ? (
            <label>
              {t.applyPhone}
              {spec.phone.required ? null : <span className="hint">{t.adOptional}</span>}
              <input type="tel" value={phone} maxLength={40} required={spec.phone.required} onChange={(event) => { setPhoneEdited(true); setPhone(event.target.value); }} />
            </label>
          ) : null}
          {spec.email.enabled ? (
            <label>
              {t.applyEmail}
              {spec.email.required ? null : <span className="hint">{t.adOptional}</span>}
              <input type="email" value={email} maxLength={120} required={spec.email.required} onChange={(event) => { setEmailEdited(true); setEmail(event.target.value); }} />
            </label>
          ) : null}
          {spec.questions.map((question) => (
            <label key={question.id || question.text}>
              {question.text}
              {question.required ? null : <span className="hint">{t.adOptional}</span>}
              <textarea
                value={answers[question.id] || ""}
                maxLength={2000}
                required={question.required}
                rows={3}
                onChange={(event) => setAnswers((currentAnswers) => ({ ...currentAnswers, [question.id]: event.target.value }))}
              />
            </label>
          ))}
          {spec.cv.enabled ? (
            <label>
              {t.applyCv}
              <span className="hint">{spec.cv.required ? t.fieldRequired : t.adOptional}. {t.applyCvHint}</span>
              <input
                type="file"
                required={spec.cv.required}
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
          ) : null}
          {showConsents && consentPayload ? (
            <ConsentFields
              payload={consentPayload}
              grants={grants}
              visibility={consentPayload.visibility || "anonymous"}
              onGrantChange={(kind, value) => setGrants((current) => ({ ...current, [kind]: value }))}
              onVisibilityChange={() => {}}
              showVisibility={false}
              idPrefix={`apply-consent-${jobId}`}
            />
          ) : null}
          <div className="ad-actions">
            <button type="submit" className="btn primary" disabled={busy}>{t.applySend}</button>
            {hasOriginal ? (
              <button type="button" className="btn red" onClick={() => openLink("original")}>{t.original}</button>
            ) : null}
          </div>
        </form>
      ) : null}
      {!onsite ? (
        <div className="actions">
          <button type="button" className="btn primary" onClick={() => openLink("apply")}>
            {t.apply}
          </button>
          {hasOriginal ? (
            <button type="button" className="btn red" onClick={() => openLink("original")}>
              {t.original}
            </button>
          ) : null}
        </div>
      ) : null}
      {onsite && current && hasOriginal ? (
        <div className="actions">
          <button type="button" className="btn red" onClick={() => openLink("original")}>{t.original}</button>
        </div>
      ) : null}
      {open ? (
        <p className="note" role="status">
          {t.locked}
        </p>
      ) : null}
      <ApplicationList
        locale={locale}
        title={t.myApplications}
        items={mine}
        hideEmpty
        mode="candidate"
        onChanged={() => setReloadKey((value) => value + 1)}
      />
    </>
  );
}
