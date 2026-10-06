import { AdminPage } from "../../../components/admin-page";
import { getAdmin } from "../../../lib/server/admin";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getAdmin();
  return (
    <AdminPage
      locale="en"
      initialJobs={initial.jobs}
      initialApplications={initial.applications}
      initialCrawled={initial.crawled}
      initialAiFlags={initial.aiFlags}
    />
  );
}
