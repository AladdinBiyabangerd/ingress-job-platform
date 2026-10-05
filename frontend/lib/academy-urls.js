/** Ingress Academy deep-link helpers (trainings + career paths). */

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
