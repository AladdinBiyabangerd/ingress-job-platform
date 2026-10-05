import { TrendsPage } from "../../components/trends";
import { fetchTrends } from "../../lib/api";
import { trendsMetadata } from "../../lib/seo";

export const revalidate = 60;

export function generateMetadata() {
  return trendsMetadata("az");
}

export default async function Page() {
  let data = null;
  let error = false;
  try {
    data = await fetchTrends({ lang: "az" });
  } catch {
    error = true;
  }
  return <TrendsPage locale="az" data={data} error={error} />;
}
