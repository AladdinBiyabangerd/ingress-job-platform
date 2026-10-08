import { TalentSearch } from "../../components/talent-search";
import { getTalentSearch } from "../../lib/server/talent";
import { privatePageMetadata } from "../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getTalentSearch();
  return <TalentSearch locale="az" initial={initial} />;
}
