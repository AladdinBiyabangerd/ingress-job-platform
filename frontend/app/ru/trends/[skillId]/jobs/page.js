import { notFound } from "next/navigation";
import { TrendJobsPage } from "../../../../../components/trend-jobs";
import { clampTrendsWindow } from "../../../../../components/trends";
import { getTrendDetail } from "../../../../../lib/server/trends";
import { trendSkillMetadata } from "../../../../../lib/seo";

export const revalidate = 60;

const JOBS_PER_PAGE = 20;

export async function generateMetadata({ params }) {
  const route = (await params) || {};
  const skillId = Number.parseInt(String(route.skillId || ""), 10);
  if (!Number.isFinite(skillId) || skillId <= 0) {
    return { robots: { index: false, follow: false } };
  }
  try {
    const data = await getTrendDetail(skillId, { lang: "ru", windowDays: 7 });
    if (!data) return { robots: { index: false, follow: false } };
    return trendSkillMetadata("ru", data, { jobs: true });
  } catch {
    return { robots: { index: false, follow: false } };
  }
}

function one(value) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function Page({ params, searchParams }) {
  const route = (await params) || {};
  const query = (await searchParams) || {};
  const skillId = Number.parseInt(String(route.skillId || ""), 10);
  if (!Number.isFinite(skillId) || skillId <= 0) notFound();
  const windowDays = clampTrendsWindow(one(query.days));
  const page = Math.max(1, Number.parseInt(String(one(query.page) || "1"), 10) || 1);
  let data = null;
  let error = false;
  try {
    data = await getTrendDetail(skillId, {
      lang: "ru",
      windowDays,
      jobsLimit: JOBS_PER_PAGE,
      jobsPage: page,
    });
    if (!data) notFound();
  } catch {
    error = true;
  }
  return <TrendJobsPage locale="ru" data={data} error={error} page={page} />;
}
