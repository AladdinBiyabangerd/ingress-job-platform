import { TrendsPage, clampTrendsWindow } from "../../components/trends";
import { fetchTrends } from "../../lib/api";
import { trendsMetadata } from "../../lib/seo";

export const revalidate = 60;

export function generateMetadata() {
  return trendsMetadata("az");
}

function one(value) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function Page({ searchParams }) {
  const params = (await searchParams) || {};
  const page = Math.min(1000, Math.max(1, Number.parseInt(String(one(params.page) || "1"), 10) || 1));
  const windowDays = clampTrendsWindow(one(params.days));
  let data = null;
  let error = false;
  try {
    data = await fetchTrends({ lang: "az", windowDays });
  } catch {
    error = true;
  }
  return <TrendsPage locale="az" data={data} error={error} page={page} windowDays={windowDays} />;
}
