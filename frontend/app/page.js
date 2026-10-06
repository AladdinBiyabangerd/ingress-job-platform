import { Home } from "../components/home";
import { JsonLd } from "../components/json-ld";
import { loadHomeJobs } from "../lib/server/jobs";
import { homeJsonLd, homeMetadata } from "../lib/seo";

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return homeMetadata("az");
}

export default async function Page() {
  const jsonLd = homeJsonLd("az");
  const { data, error } = await loadHomeJobs();
  return (
    <>
      <JsonLd data={jsonLd} />
      <Home
        locale="az"
        jobs={data.items}
        total={data.total}
        catalogTotal={data.catalog_total}
        pages={data.pages}
        facets={data.facets}
        error={error}
      />
    </>
  );
}
