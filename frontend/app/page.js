import { Home } from "../components/home";
import { JsonLd } from "../components/json-ld";
import { getJobs } from "../lib/server/jobs";
import { homeJsonLd, homeMetadata } from "../lib/seo";

export const revalidate = 60;

export function generateMetadata() {
  return homeMetadata("az");
}

function emptyPayload() {
  return {
    items: [],
    total: 0,
    pages: 1,
    catalog_total: 0,
    facets: { languages: [], categories: [], stacks: [] },
  };
}

export default async function Page() {
  const jsonLd = homeJsonLd("az");
  try {
    const data = await getJobs("{}");
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
          error={false}
        />
      </>
    );
  } catch {
    const data = emptyPayload();
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
          error
        />
      </>
    );
  }
}
