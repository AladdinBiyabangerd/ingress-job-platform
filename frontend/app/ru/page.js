import { Home } from "../../components/home";
import { getJobs } from "../../lib/server/jobs";
import { homeMetadata } from "../../lib/seo";

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return homeMetadata("ru");
}

export default async function Page() {
  try {
    const jobs = await getJobs();
    return <Home locale="ru" jobs={jobs} error={false} />;
  } catch {
    return <Home locale="ru" jobs={[]} error />;
  }
}
