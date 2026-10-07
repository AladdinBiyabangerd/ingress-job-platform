import { notFound } from "next/navigation";
import { TrendDetailPage } from "../../../components/trend-detail";
import { clampTrendsWindow } from "../../../components/trends";
import { getTrendDetail } from "../../../lib/server/trends";
import { trendsMetadata } from "../../../lib/seo";

export const revalidate = 60;

export function generateMetadata() {
  return trendsMetadata("az");
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
  let data = null;
  let error = false;
  try {
    data = await getTrendDetail(skillId, { lang: "az", windowDays });
    if (!data) notFound();
  } catch {
    error = true;
  }
  return <TrendDetailPage locale="az" data={data} error={error} />;
}
