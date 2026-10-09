import { InsightsRoadmap } from "../../../../../components/roadmap";
import { getInsightsBundle } from "../../../../../lib/server/insights";
import { privatePageMetadata } from "../../../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getInsightsBundle("ru");
  return <InsightsRoadmap locale="ru" initialInsights={initial.insights} />;
}
