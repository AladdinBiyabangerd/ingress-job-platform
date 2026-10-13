import { AdminPage } from "../../../components/admin-page";
import { getAdmin } from "../../../lib/server/admin";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page({ searchParams }) {
  const query = (await searchParams) || {};
  const initial = await getAdmin();
  return (
    <AdminPage
      locale="ru"
      initialTab={typeof query.tab === "string" ? query.tab : "queue"}
      initialJobs={initial.jobs}
      initialCrawled={initial.crawled}
      initialAiFlags={initial.aiFlags}
    />
  );
}
