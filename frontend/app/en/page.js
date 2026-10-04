import { Home } from "../../components/home";
import { fetchJobs } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function Page() {
  try {
    const jobs = await fetchJobs();
    return <Home locale="en" jobs={jobs} error={false} />;
  } catch {
    return <Home locale="en" jobs={[]} error />;
  }
}
