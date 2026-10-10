/**
 * "CV check" tab helpers. Everything is derived from the real parse result
 * (profile fields + profile.parse_meta written by the worker), never from a
 * CV template/style.
 */

/** Section-by-section completeness of the form values (pure, unit-tested). */
export function cvChecks({ fullName, email, phone, city, headline, work, education, skills, languages }) {
  const jobs = Array.isArray(work) ? work : [];
  const datedJobs = jobs.filter((job) => job?.start);
  const has = (v) => Boolean(String(v || "").trim());
  return [
    { id: "name", ok: has(fullName) },
    { id: "contact", ok: has(email) && (has(phone) || has(city)) },
    { id: "headline", ok: has(headline) },
    { id: "work", ok: jobs.length > 0 && datedJobs.length === jobs.length },
    { id: "education", ok: (education || []).length > 0 },
    { id: "skills", ok: (skills || []).length >= 3 },
    { id: "languages", ok: (languages || []).length > 0 },
  ];
}

const KNOWN_ISSUES = new Set([
  "name_missing", "name_suspicious", "contact_missing", "city_is_education",
  "headline_missing", "headline_suspicious", "work_missing", "work_undated",
  "work_garbage_title", "work_missing_company", "work_date_order", "work_future_date",
  "education_missing", "skills_thin", "text_too_short",
]);

/** Which tab/field the "Fix" button of an issue should open. */
export function issueTarget(code) {
  if (code.startsWith("work_") || code === "skills_thin") return "work";
  if (code.startsWith("education")) return "education";
  if (code.startsWith("headline")) return "headline";
  return "name";
}

const num = (v) => (typeof v === "number" && Number.isFinite(v) ? Math.max(0, Math.min(1, v)) : null);

/** Dynamic feedback from parse_meta. Returns null when the CV has no quality data (old profiles). */
export function cvFeedback(meta) {
  const q = meta && typeof meta === "object" ? meta.quality : null;
  const score = num(q?.score);
  if (score === null) return null;
  const threshold = num(q?.threshold) ?? 0.65;
  const src = ["rules", "ai", "mixed"].includes(meta.parse_source) ? meta.parse_source : "rules";
  let ai = "none";
  if (meta.ai_fallback === "applied") ai = "applied";
  else if (meta.ai_fallback === "failed") ai = "failed";
  else if (meta.ai_fallback === "skipped") ai = "skipped";
  const issues = (Array.isArray(q.issues) ? q.issues : []).filter((c) => KNOWN_ISSUES.has(c));
  return {
    score,
    before: num(q.score_before),
    threshold,
    source: src,
    ai,
    issues,
    level: score >= threshold ? (issues.length ? "partial" : "ok") : "low",
  };
}
