/**
 * Temporary product surfaces. Flip to true (or set NEXT_PUBLIC_* = 1) to re-enable.
 * Defaults off — recommendations, roadmap, and employer posting are parked.
 */

function envOn(name) {
  const raw = String(process.env[name] || "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
}

/** Candidate role/job recommendations hub (`/me/recommendations`). */
export function recommendationsEnabled() {
  if (envOn("NEXT_PUBLIC_PRODUCT_RECOMMENDATIONS_ENABLED")) return true;
  return false;
}

/** Learning roadmap / insights hub (`/me/insights/*`). */
export function roadmapEnabled() {
  if (envOn("NEXT_PUBLIC_PRODUCT_ROADMAP_ENABLED")) return true;
  return false;
}

/** Employer post / company / talent surfaces (`/post`, `/company`, `/talent`). */
export function employerPostingEnabled() {
  if (envOn("NEXT_PUBLIC_PRODUCT_EMPLOYER_POSTING_ENABLED")) return true;
  return false;
}
