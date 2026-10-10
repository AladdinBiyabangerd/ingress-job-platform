"use client";

import { useEffect, useRef, useState } from "react";
import { beginLogin } from "../../lib/auth-link";
import { hrefFor, text } from "../../lib/copy";
import { LoginLink } from "../login-link";

const POLL_MS = 2500;
const POLL_MAX = 20;

function pct(score) {
  if (typeof score !== "number" || !Number.isFinite(score)) return null;
  return Math.max(0, Math.min(100, Math.round(score * 100)));
}

function ScoreRing({ percent }) {
  const size = 88;
  const stroke = 7;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, percent ?? 0));
  const offset = c * (1 - clamped / 100);
  return (
    <svg className="jd-analyze-ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke} />
      <circle
        className="jd-analyze-ring-progress"
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--brand)"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="jd-analyze-ring-value">
        {percent == null ? "—" : `${clamped}%`}
      </text>
    </svg>
  );
}

function ListBlock({ title, items, empty }) {
  const list = Array.isArray(items) ? items.filter(Boolean) : [];
  return (
    <div className="jd-analyze-block">
      <h3 className="jd-analyze-block-title">{title}</h3>
      {list.length ? (
        <ul className="jd-analyze-list">
          {list.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="jd-analyze-empty">{empty}</p>
      )}
    </div>
  );
}

function aiErrorMessage(t, code) {
  const raw = String(code || "").trim();
  if (!raw || raw === "ai_pending") return "";
  if (raw === "job_analyze_disabled" || raw === "ai_disabled") return t.jdAnalyzeAiOff;
  if (raw === "ai_no_key") return t.jdAnalyzeErrorNoKey;
  if (raw.includes("budget")) return t.jdAnalyzeErrorBudget;
  if (raw.includes("provider") || raw === "ai_failed") return t.jdAnalyzeErrorProvider;
  if (raw === "ai_validation_failed") return t.jdAnalyzeErrorValidation;
  return t.jdAnalyzeErrorCode(raw);
}

export function JobDetailAnalyzePanel({ locale, jobId, returnTo, open, preview = false }) {
  const t = text(locale);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const pollLeft = useRef(0);

  useEffect(() => {
    if (!open || preview || !jobId) return undefined;
    let cancelled = false;
    let timer = 0;
    setLoading(true);
    setError("");
    setPayload(null);
    pollLeft.current = POLL_MAX;

    async function load() {
      const qs = new URLSearchParams({ lang: locale || "az" });
      const res = await fetch(`/api/auth/me/jobs/${jobId}/analyze?${qs}`, { cache: "no-store" });
      if (res.status === 401 || res.status === 403) {
        beginLogin({ intent: "job_candidate", returnTo });
        return null;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error("load");
      return data;
    }

    function schedulePoll() {
      if (cancelled || pollLeft.current <= 0) return;
      timer = window.setTimeout(async () => {
        if (cancelled) return;
        pollLeft.current -= 1;
        try {
          const next = await load();
          if (cancelled || !next) return;
          setPayload(next);
          if (next.ai_pending) schedulePoll();
        } catch {
          /* keep last payload */
        }
      }, POLL_MS);
    }

    load()
      .then((data) => {
        if (cancelled) return;
        setPayload(data);
        setLoading(false);
        if (data?.ai_pending) schedulePoll();
      })
      .catch(() => {
        if (!cancelled) {
          setError(t.loadError);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [open, preview, jobId, locale, returnTo, t.loadError]);

  if (!open) return null;

  const profileHref = hrefFor(locale, { mode: "profile" });
  const gate = payload?.gate;
  const fit = payload?.fit;
  const report = payload?.report;
  const scorePct = pct(fit?.score);
  const confPct = pct(fit?.confidence);
  const components = fit?.components && typeof fit.components === "object" ? fit.components : {};
  const aiMsg = aiErrorMessage(t, payload?.ai_error);
  const pending = Boolean(payload?.ai_pending) || (loading && !payload);

  return (
    <section
      id="jd-analyze-panel"
      className="jd-analyze"
      aria-labelledby="jd-analyze-title"
      aria-busy={pending || undefined}
    >
      <div className="jd-analyze-head">
        <h2 id="jd-analyze-title">{t.jdAnalyzeTitle}</h2>
        {pending ? (
          <p className="jd-analyze-status" role="status">
            {t.jdAnalyzePending}
          </p>
        ) : null}
      </div>

      {preview ? <p className="jd-analyze-gate">{t.jdAnalyzePreview}</p> : null}
      {error ? <p className="jd-analyze-error">{error}</p> : null}

      {!preview && gate === "consent_required" ? (
        <div className="jd-analyze-gate">
          <p>{t.jdAnalyzeConsent}</p>
          <a className="jd-btn jd-btn-outline" href={profileHref}>
            {t.jdAnalyzeConsentCta}
          </a>
        </div>
      ) : null}

      {!preview && gate === "skills_required" ? (
        <div className="jd-analyze-gate">
          <p>{t.jdAnalyzeSkills}</p>
          <a className="jd-btn jd-btn-outline" href={hrefFor(locale, { mode: "profileReview" })}>
            {t.jdAnalyzeSkillsCta}
          </a>
        </div>
      ) : null}

      {!preview && fit ? (
        <>
          <div className="jd-analyze-score-row">
            <ScoreRing percent={scorePct} />
            <div className="jd-analyze-score-meta">
              <p className="jd-analyze-score-label">{t.jdAnalyzeScore}</p>
              {confPct != null ? (
                <p className="jd-analyze-confidence">
                  {t.jdAnalyzeConfidence}: {confPct}%
                </p>
              ) : null}
              {fit.explanation ? <p className="jd-analyze-explanation">{fit.explanation}</p> : null}
            </div>
          </div>

          <div className="jd-analyze-breakdown" aria-label={t.jdAnalyzeBreakdown}>
            {[
              ["skills", t.jdAnalyzeCompSkills],
              ["seniority", t.jdAnalyzeCompSeniority],
              ["location", t.jdAnalyzeCompLocation],
              ["language", t.jdAnalyzeCompLanguage],
              ["freshness", t.jdAnalyzeCompFreshness],
            ].map(([key, label]) => {
              const value = pct(components[key]);
              return (
                <div key={key} className="jd-analyze-comp">
                  <span>{label}</span>
                  <strong>{value == null ? "—" : `${value}%`}</strong>
                </div>
              );
            })}
          </div>

          <div className="jd-analyze-grid">
            <ListBlock title={t.jdAnalyzeSkillsMatch} items={fit.have} empty={t.jdAnalyzeListEmpty} />
            <ListBlock title={t.jdAnalyzeSkillsMissing} items={fit.missing} empty={t.jdAnalyzeListEmpty} />
          </div>

          {report ? (
            <div className="jd-analyze-report">
              {report.summary ? (
                <div className="jd-analyze-block">
                  <h3 className="jd-analyze-block-title">{t.jdAnalyzeSummary}</h3>
                  <p className="jd-analyze-prose">{report.summary}</p>
                </div>
              ) : null}

              <div className="jd-analyze-grid">
                <ListBlock
                  title={t.jdAnalyzeSkillsUnverified}
                  items={report.skills?.unverified}
                  empty={t.jdAnalyzeListEmpty}
                />
                <ListBlock
                  title={t.jdAnalyzeReqsMatch}
                  items={report.requirements?.matching}
                  empty={t.jdAnalyzeListEmpty}
                />
                <ListBlock
                  title={t.jdAnalyzeReqsMissing}
                  items={report.requirements?.missing}
                  empty={t.jdAnalyzeListEmpty}
                />
                <ListBlock
                  title={t.jdAnalyzeReqsUnverified}
                  items={report.requirements?.unverified}
                  empty={t.jdAnalyzeListEmpty}
                />
              </div>

              {report.facts ? (
                <div className="jd-analyze-block">
                  <h3 className="jd-analyze-block-title">{t.jdAnalyzeFacts}</h3>
                  <dl className="jd-analyze-facts">
                    <div>
                      <dt>{t.jdAnalyzeSalary}</dt>
                      <dd>{report.facts.salary}</dd>
                    </div>
                    <div>
                      <dt>{t.jdAnalyzeLocation}</dt>
                      <dd>{report.facts.location}</dd>
                    </div>
                    <div>
                      <dt>{t.jdAnalyzeRemote}</dt>
                      <dd>{report.facts.remote}</dd>
                    </div>
                    <div>
                      <dt>{t.jdAnalyzeVisa}</dt>
                      <dd>{report.facts.visa}</dd>
                    </div>
                    <div>
                      <dt>{t.jdAnalyzeRelocation}</dt>
                      <dd>{report.facts.relocation}</dd>
                    </div>
                  </dl>
                </div>
              ) : null}

              <ListBlock
                title={t.jdAnalyzeExperiences}
                items={report.experiences_to_emphasize}
                empty={t.jdAnalyzeListEmpty}
              />
              <ListBlock title={t.jdAnalyzeCvAdapt} items={report.cv_adapt} empty={t.jdAnalyzeListEmpty} />
              {report.apply_tip ? (
                <div className="jd-analyze-block">
                  <h3 className="jd-analyze-block-title">{t.jdAnalyzeApplyTip}</h3>
                  <p className="jd-analyze-prose">{report.apply_tip}</p>
                </div>
              ) : null}
            </div>
          ) : null}

          {!pending && aiMsg ? <p className="jd-analyze-note">{aiMsg}</p> : null}
        </>
      ) : null}

      {!preview && !loading && !gate && !fit && !error ? (
        <div className="jd-analyze-gate">
          <p>{t.jdAnalyzeGuest}</p>
          <LoginLink className="jd-btn jd-btn-outline" intent="job_candidate" returnTo={returnTo}>
            {t.jdAnalyzeGuestCta}
          </LoginLink>
        </div>
      ) : null}
    </section>
  );
}
