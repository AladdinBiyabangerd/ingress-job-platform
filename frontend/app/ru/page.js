import { Home } from "../../components/home";
import { fetchJobs } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function Page() {
  try {
    const jobs = await fetchJobs();
    return <Home locale="ru" jobs={jobs} error={false} />;
  } catch {
    return <Home locale="ru" jobs={[]} error />;
  }
}
