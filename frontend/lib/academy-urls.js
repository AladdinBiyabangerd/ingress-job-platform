/** Ingress Academy deep-link helpers (trainings + career paths). */

const COURSE_ACRONYMS = new Set([
  "ai",
  "api",
  "aws",
  "cka",
  "css",
  "html",
  "llm",
  "oca",
  "rhcsa",
  "se",
  "sql",
  "sre",
]);

const COURSE_SMALL = new Set(["and", "for", "from", "of", "to", "with"]);

/** Human label from a training slug, e.g. java-se-oca-az → "Java SE OCA". */
export function academyCourseLabel(courseId) {
  const id = String(courseId || "").trim().replace(/^\/+|\/+$/g, "");
  if (!id) return "";
  const slug = id.replace(/-(az|en|ru)$/i, "");
  const words = slug.split(/[-_]+/).filter(Boolean);
  if (!words.length) return id;
  return words
    .map((word, index) => {
      const lower = word.toLowerCase();
      if (COURSE_ACRONYMS.has(lower)) return lower.toUpperCase();
      if (index > 0 && COURSE_SMALL.has(lower)) return lower;
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(" ");
}

export function academyCourseUrl(courseId, { utmMedium = "skill_gap" } = {}) {
  const id = String(courseId || "").trim().replace(/^\/+|\/+$/g, "");
  if (!id) return "";
  const base = (
    process.env.NEXT_PUBLIC_ACADEMY_COURSE_BASE || "https://ingress.academy/trainings/"
  ).replace(/\/?$/, "/");
  const url = new URL(`${base}${encodeURIComponent(id)}/`);
  url.searchParams.set("utm_source", "ingress_job");
  url.searchParams.set("utm_medium", String(utmMedium || "skill_gap"));
  url.searchParams.set("utm_campaign", "academy_cross_sell");
  return url.toString();
}

export function academyCareerPathUrl(pathId, { utmMedium = "skill_gap" } = {}) {
  const id = String(pathId || "").trim().replace(/^\/+|\/+$/g, "");
  if (!id) return "";
  const base = (
    process.env.NEXT_PUBLIC_ACADEMY_CAREER_PATH_BASE ||
    "https://ingress.academy/career-paths/"
  ).replace(/\/?$/, "/");
  const url = new URL(`${base}${encodeURIComponent(id)}/`);
  url.searchParams.set("utm_source", "ingress_job");
  url.searchParams.set("utm_medium", String(utmMedium || "skill_gap"));
  url.searchParams.set("utm_campaign", "academy_cross_sell");
  return url.toString();
}
