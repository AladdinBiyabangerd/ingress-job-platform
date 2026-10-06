import { PostPage } from "../../components/post-page";
import { getCabinet } from "../../lib/server/cabinet";
import { privatePageMetadata } from "../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getCabinet();
  return <PostPage locale="az" initialJobs={initial.jobs} initialApplications={initial.applications} />;
}
