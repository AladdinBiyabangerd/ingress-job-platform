import { notFound } from "next/navigation";
import { JobDetail } from "../../../components/job-detail";
import { fetchJob } from "../../../lib/api";

export const dynamic = "force-dynamic";

export default async function Page({ params }) {
  const { id } = await params;
  let job = null;
  try {
    job = await fetchJob(id);
  } catch {
    throw new Error("job api unavailable");
  }
  if (!job) notFound();
  return <JobDetail locale="az" job={job} />;
}
