import { TrendsPage } from "../../../components/trends";
import { fetchTrends } from "../../../lib/api";
import { trendsMetadata } from "../../../lib/seo";

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return trendsMetadata("ru");
}

export default async function Page() {
  let data = null;
  let error = false;
  try {
    data = await fetchTrends({ lang: "ru" });
  } catch {
    error = true;
  }
  return <TrendsPage locale="ru" data={data} error={error} />;
}
