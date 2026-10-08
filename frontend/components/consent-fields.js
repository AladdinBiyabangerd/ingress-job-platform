"use client";

/** Consent checkboxes + visibility radios; copy comes from /api/auth/consents. */
export function ConsentFields({
  payload,
  grants,
  visibility,
  onGrantChange,
  onVisibilityChange,
  showVisibility = true,
  showMeta = true,
  idPrefix = "consent",
}) {
  if (!payload) return null;
  const items = Array.isArray(payload.consents) ? payload.consents : [];
  const levels = Array.isArray(payload.visibility_levels) ? payload.visibility_levels : [];

  return (
    <fieldset className="consent-fields">
      {showMeta && payload.intro ? <p className="hint">{payload.intro}</p> : null}
      {showMeta && payload.legal_disclaimer ? <p className="hint consent-legal">{payload.legal_disclaimer}</p> : null}
      {items.map((item) => (
        <div key={item.kind} className="consent-item">
          <label className="inline" htmlFor={`${idPrefix}-${item.kind}`}>
            <input
              id={`${idPrefix}-${item.kind}`}
              type="checkbox"
              checked={Boolean(grants[item.kind])}
              onChange={(event) => onGrantChange(item.kind, event.target.checked)}
            />
            <span>{item.checkbox_label}</span>
          </label>
          {item.short_help ? <p className="hint">{item.short_help}</p> : null}
        </div>
      ))}
      {showVisibility && levels.length ? (
        <div className="consent-visibility">
          {levels.map((level) => (
            <label key={level.id} className="inline" htmlFor={`${idPrefix}-vis-${level.id}`}>
              <input
                id={`${idPrefix}-vis-${level.id}`}
                type="radio"
                name={`${idPrefix}-visibility`}
                checked={visibility === level.id}
                onChange={() => onVisibilityChange(level.id)}
              />
              <span>
                {level.label}
                {level.description ? <span className="hint"> — {level.description}</span> : null}
              </span>
            </label>
          ))}
        </div>
      ) : null}
    </fieldset>
  );
}

export function grantsFromPayload(payload) {
  const out = { matching: false, emails: false, recruiter_visibility: false };
  for (const item of payload?.consents || []) {
    if (item?.kind in out) out[item.kind] = Boolean(item.granted);
  }
  return out;
}
