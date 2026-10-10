"use client";

import { cvChecks, cvFeedback, issueTarget } from "../lib/cv-quality";
import { CV_STYLES, CV_TEMPLATES, detectedTemplate, pick, templatesByStyle } from "../lib/cv-styles";

const pct = (n) => `${Math.round(n * 100)}%`;

/** "CV check" tab: how the uploaded CV was actually read (score, source, issues). */
export function ProfileReviewCvCheck({ t, locale = "az", values, confidence, parseMeta, onJump }) {
  const checks = cvChecks(values);
  const failed = checks.filter((item) => !item.ok);
  const fb = cvFeedback(parseMeta);
  const tpl = detectedTemplate(parseMeta);
  const activeStyle = tpl?.style?.id || null;

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
              {fb.aiSkippedUnreadable ? (
                <p className="hint">{t.profileReviewCvAiSkippedShort}</p>
              ) : fb.ai === "failed" || fb.ai === "skipped" ? (
                <p className="hint">{t.profileReviewCvAiUnavailable}</p>
              ) : null}
              {fb.issues.length ? (
                <>
                  <p className="hint">{t.profileReviewCvIssuesTitle}</p>
                  <ul className="cvcheck-tips">
                    {fb.issues.map((code) => (
                      <li key={code}>
                        {t.profileReviewCvIssues[code]}{" "}
                        {onJump && code !== "text_too_short" && code !== "text_garbled" && code !== "placeholder_text" ? (
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
        <section className="review-panel cvcheck-templates-panel">
          <header className="review-panel-head">
            <h2>{t.profileReviewCvTemplateTitle}</h2>
          </header>
          <p className="cvcheck-detected" data-template={tpl?.id || "none"}>
            {!tpl
              ? t.profileReviewCvTemplateOld
              : tpl.id
                ? t.profileReviewCvTemplateDetected(tpl.name)
                : t.profileReviewCvTemplateNone}
          </p>
          {tpl?.id ? (
            <p className="hint">{tpl.applied ? t.profileReviewCvTemplateApplied : t.profileReviewCvTemplateNotApplied}</p>
          ) : null}
        </section>
        <section className="review-panel cvcheck-styles-panel">
          <header className="review-panel-head">
            <h2>{t.profileReviewCvStylesTitle}</h2>
          </header>
          <p className="hint">{t.profileReviewCvStylesHint}</p>
          <ul className="cvcheck-styles">
            {CV_STYLES.map((style) => (
              <li key={style.id} className={`cvcheck-style-card${activeStyle === style.id ? " active" : ""}`}>
                <div className="cvcheck-style-head">
                  <strong>{pick(style.name, locale)}</strong>
                  <span className={`cvcheck-badge ${style.reading === "good" ? "ok" : "partial"}`}>
                    {t.profileReviewCvReading[style.reading]}
                  </span>
                  {activeStyle === style.id ? <span className="cvcheck-badge">{t.profileReviewCvStyleYours}</span> : null}
                </div>
                <p className="hint">{pick(style.desc, locale)}</p>
                <ul className="cvcheck-tips">
                  {style.tips.map((tip, i) => (
                    <li key={i}>{pick(tip, locale)}</li>
                  ))}
                </ul>
                <ul className="cvcheck-template-list">
                  {templatesByStyle(style.id).map((item) => (
                    <li key={item.id} className={tpl?.id === item.id ? "active" : ""}>
                      <span className="cvcheck-template-name">{item.name}</span>{" "}
                      <span className="cvcheck-fmt">{item.format.toUpperCase()}</span>{" "}
                      <span className={`cvcheck-badge ${item.reading === "good" ? "ok" : "partial"}`}>
                        {t.profileReviewCvReading[item.reading]}
                      </span>
                      <p className="hint">{pick(item.desc, locale)}</p>
                      <p className="hint">{pick(item.tip, locale)}</p>
                      <p className="hint cvcheck-source">{t.profileReviewCvTemplateSource(item.source, item.license)}</p>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
          <p className="hint">{t.profileReviewCvTemplatesToggle(CV_TEMPLATES.length)}</p>
        </section>
      </div>
    </div>
  );
}
