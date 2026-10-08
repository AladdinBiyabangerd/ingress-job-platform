import { MySaved } from "../../../components/my-saved";
import { getSavedJobs } from "../../../lib/server/saved-jobs";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getSavedJobs();
  return (
    <MySaved
      locale="en"
      initialItems={initial.items}
      initialIds={initial.ids}
      initialTotal={initial.total}
      initialPages={initial.pages}
    />
  );
}
