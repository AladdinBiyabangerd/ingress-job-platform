import { notFound } from "next/navigation";
import { JobDetail } from "../../../../components/job-detail";
import { getJob } from "../../../../lib/server/jobs";
import { jobMetadata } from "../../../../lib/seo";

export const revalidate = 60;

export async function generateMetadata({ params }) {
  const { id } = await params;
  try {
    const job = await getJob(id);
    if (!job) return { robots: { index: false, follow: false } };
    return jobMetadata("en", job);
  } catch {
    return { robots: { index: false, follow: false } };
  }
}

export default async function Page({ params }) {
  const { id } = await params;
  let job = null;
  try {
    job = await getJob(id);
  } catch {
    throw new Error("job api unavailable");
  }
  if (!job) notFound();
  return <JobDetail locale="en" job={job} />;
}
