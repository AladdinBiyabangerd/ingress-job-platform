import { Home } from "../components/home";
import { getJobs } from "../lib/server/jobs";
import { homeMetadata } from "../lib/seo";

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return homeMetadata("az");
}

export default async function Page() {
  try {
    const jobs = await getJobs();
    return <Home locale="az" jobs={jobs} error={false} />;
  } catch {
    return <Home locale="az" jobs={[]} error />;
  }
}
