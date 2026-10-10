"use client";

import { cvChecks, cvFeedback, issueTarget } from "../lib/cv-quality";

const pct = (n) => `${Math.round(n * 100)}%`;

/** "CV check" tab: how the uploaded CV was actually read (score, source, issues). */
export function ProfileReviewCvCheck({ t, values, confidence, parseMeta, onJump }) {
  const checks = cvChecks(values);
  const failed = checks.filter((item) => !item.ok);
  const fb = cvFeedback(parseMeta);

  return (
    <div
      className="profile-review-pane profile-review-pane-cvcheck"
      role="tabpanel"
      id="profile-review-panel-cvcheck"
      aria-labelledby="profile-review-tab-cvcheck"
    >
      <div className="profile-review-col">
        <section className="review-panel">
          <header className="review-panel-head">
            <h2>{t.profileReviewCvReadTitle}</h2>
            {typeof confidence === "number" ? (
              <span className="hint">{t.profileReviewConfidence(confidence)}</span>
            ) : null}
          </header>
          <p className="hint">{failed.length ? t.profileReviewCvReadMissing(failed.length) : t.profileReviewCvReadAll}</p>
          <ul className="cvcheck-list">
            {checks.map((item) => (
              <li key={item.id} className={item.ok ? "ok" : "warn"}>
                <span className="cvcheck-dot" aria-hidden="true" />
                <span>{t.profileReviewCvChecks[item.id]}</span>
                {!item.ok && onJump ? (
                  <button type="button" className="btn ghost small" onClick={() => onJump(item.id)}>
                    {t.profileReviewCvFix}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      </div>
      <div className="profile-review-col">
        <section className="review-panel">
          <header className="review-panel-head">
            <h2>{t.profileReviewCvQualityTitle}</h2>
          </header>
          {!fb ? (
            <p className="hint">{t.profileReviewCvQualityNone}</p>
          ) : (
            <div className="cvcheck-style">
              <p>
                <span className={`cvcheck-badge ${fb.level === "ok" ? "ok" : "partial"}`}>
                  {t.profileReviewCvQualityScore(pct(fb.score))}
                </span>{" "}
                {t.profileReviewCvLevel[fb.level]}
              </p>
              <p className="hint">{t.profileReviewCvSource[fb.source]}</p>
              {fb.ai === "applied" && fb.before !== null ? (
                <p className="hint">{t.profileReviewCvAiApplied(pct(fb.before), pct(fb.score))}</p>
              ) : null}
              {fb.ai === "failed" || fb.ai === "skipped" ? (
                <p className="hint">{t.profileReviewCvAiUnavailable}</p>
              ) : null}
              {fb.issues.length ? (
                <>
                  <p className="hint">{t.profileReviewCvIssuesTitle}</p>
                  <ul className="cvcheck-tips">
                    {fb.issues.map((code) => (
                      <li key={code}>
                        {t.profileReviewCvIssues[code]}{" "}
                        {onJump && code !== "text_too_short" ? (
                          <button type="button" className="btn ghost small" onClick={() => onJump(issueTarget(code))}>
                            {t.profileReviewCvFix}
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
