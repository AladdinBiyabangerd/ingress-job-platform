"use client";

import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";

function MatchRing({ percent }) {
  const size = 96;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = c * (1 - clamped / 100);
  return (
    <svg className="match-ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--border)"
        strokeWidth={stroke}
      />
      <circle
        className="match-ring-progress"
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
      <text
        x="50%"
        y="50%"
        dominantBaseline="central"
        textAnchor="middle"
        className="match-ring-value"
      >
        {clamped}%
      </text>
    </svg>
  );
}

/**
 * Right-rail match widget. Guest: one-line login CTA. Auth: ring + recommendations link.
 */
export function MatchAside({ locale, authenticated, topScore = null, jobTitle = "" }) {
  const t = text(locale);
  const recoHref = hrefFor(locale, { mode: "recommendations" });
  const login = loginHref({ intent: "job_candidate", returnTo: recoHref });

  if (!authenticated) {
    return (
      <aside className="side-widget match-aside match-aside-guest" aria-labelledby="match-aside-title">
        <h2 id="match-aside-title">{t.matchAsideTitle}</h2>
        <p className="match-aside-guest-line">{t.matchAsideGuest}</p>
        <a className="side-widget-link" href={login}>
          {t.matchAsideGuestCta}
        </a>
      </aside>
    );
  }

  const percent =
    typeof topScore === "number" && Number.isFinite(topScore)
      ? Math.round(topScore * 100)
      : null;

  return (
    <aside className="side-widget match-aside" aria-labelledby="match-aside-title">
      <div className="side-widget-head">
        <h2 id="match-aside-title">{t.matchAsideTitle}</h2>
      </div>
      {percent !== null ? (
        <>
          <div className="match-aside-visual">
            <MatchRing percent={percent} />
            <p className="match-aside-strength">{t.matchAsideStrong}</p>
          </div>
          <p className="match-aside-hint">
            {jobTitle ? t.matchAsideHintFor(jobTitle) : t.matchAsideHint}
          </p>
        </>
      ) : (
        <p className="match-aside-hint">{t.matchAsideEmpty}</p>
      )}
      <a className="side-widget-link" href={recoHref}>
        {t.matchAsideBreakdown}
      </a>
    </aside>
  );
}
