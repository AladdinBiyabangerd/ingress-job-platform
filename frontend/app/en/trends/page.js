import { TrendsPage } from "../../../components/trends";
import { fetchTrends } from "../../../lib/api";
import { trendsMetadata } from "../../../lib/seo";

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return trendsMetadata("en");
}

export default async function Page() {
  let data = null;
  let error = false;
  try {
    data = await fetchTrends({ lang: "en" });
  } catch {
    error = true;
  }
  return <TrendsPage locale="en" data={data} error={error} />;
}
