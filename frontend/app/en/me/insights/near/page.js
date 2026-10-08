import { InsightsNear } from "../../../../../components/insights";
import { getInsightsBundle } from "../../../../../lib/server/insights";
import { privatePageMetadata } from "../../../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getInsightsBundle("en");
  return <InsightsNear locale="en" initialInsights={initial.insights} />;
}
