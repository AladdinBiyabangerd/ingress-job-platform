import { Home } from "../../components/home";
import { JsonLd } from "../../components/json-ld";
import { loadHomeJobs } from "../../lib/server/jobs";
import { homeJsonLd, homeMetadata } from "../../lib/seo";

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return homeMetadata("en");
}

export default async function Page() {
  const jsonLd = homeJsonLd("en");
  const { data, error } = await loadHomeJobs();
  return (
    <>
      <JsonLd data={jsonLd} />
      <Home
        locale="en"
        jobs={data.items}
        total={data.total}
        pages={data.pages}
        facets={data.facets}
        error={error}
      />
    </>
  );
}
