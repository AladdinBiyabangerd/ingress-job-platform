import { notFound } from "next/navigation";
import { JsonLd } from "../../../components/json-ld";
import { TrendDetailPage } from "../../../components/trend-detail";
import { clampTrendsWindow } from "../../../components/trends";
import { getTrendDetail } from "../../../lib/server/trends";
import { trendSkillJsonLd, trendSkillMetadata } from "../../../lib/seo";

export const revalidate = 60;

export async function generateMetadata({ params }) {
  const route = (await params) || {};
  const skillId = Number.parseInt(String(route.skillId || ""), 10);
  if (!Number.isFinite(skillId) || skillId <= 0) {
    return { robots: { index: false, follow: false } };
  }
  try {
    const data = await getTrendDetail(skillId, { lang: "az", windowDays: 7 });
    if (!data) return { robots: { index: false, follow: false } };
    return trendSkillMetadata("az", data);
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
  let data = null;
  let error = false;
  try {
    data = await getTrendDetail(skillId, { lang: "az", windowDays });
    if (!data) notFound();
  } catch {
    error = true;
  }
  return (
    <>
      {data ? <JsonLd data={trendSkillJsonLd("az", data)} /> : null}
      <TrendDetailPage locale="az" data={data} error={error} />
    </>
  );
}
