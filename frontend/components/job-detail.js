import { JobDetailPage } from "./job-detail/job-detail-page";
import { jobToDetailViewModel } from "../lib/job-detail-view-model";

/**
 * Production job detail — maps API job into the shared mockup-faithful view.
 * Auth is resolved client-side inside JobDetailView actions; SSR defaults to guest
 * and CTAs update via login redirects / MeSeed-backed Save button.
 */
export function JobDetail({ locale, job, authState = "guest" }) {
  const model = jobToDetailViewModel({ locale, job, authState });
  return <JobDetailPage locale={locale} model={model} job={job} />;
}
