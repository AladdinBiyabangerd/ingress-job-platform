import { notFound } from "next/navigation";
import { TrendJobsPage } from "../../../../../components/trend-jobs";
import { clampTrendsWindow } from "../../../../../components/trends";
import { getTrendDetail } from "../../../../../lib/server/trends";
import { trendsMetadata } from "../../../../../lib/seo";

export const revalidate = 60;

const JOBS_PER_PAGE = 20;

export function generateMetadata() {
  return trendsMetadata("en");
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
      lang: "en",
      windowDays,
      jobsLimit: JOBS_PER_PAGE,
      jobsPage: page,
    });
    if (!data) notFound();
  } catch {
    error = true;
  }
  return <TrendJobsPage locale="en" data={data} error={error} page={page} />;
}
