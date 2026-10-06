import { MyApplications } from "../../../components/my-applications";
import { getMyApplications } from "../../../lib/server/applications";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getMyApplications();
  return <MyApplications locale="ru" initialItems={initial.items} />;
}
