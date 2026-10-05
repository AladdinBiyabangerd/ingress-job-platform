import { Home } from "../../components/home";
import { JsonLd } from "../../components/json-ld";
import { getJobs } from "../../lib/server/jobs";
import { homeJsonLd, homeMetadata } from "../../lib/seo";

export const revalidate = 60;

export function generateMetadata() {
  return homeMetadata("en");
}

export default async function Page() {
  const jsonLd = homeJsonLd("en");
  try {
    const jobs = await getJobs();
    return (
      <>
        <JsonLd data={jsonLd} />
        <Home locale="en" jobs={jobs} error={false} />
      </>
    );
  } catch {
    return (
      <>
        <JsonLd data={jsonLd} />
        <Home locale="en" jobs={[]} error />
      </>
    );
  }
}
