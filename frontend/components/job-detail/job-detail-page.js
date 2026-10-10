import { JsonLd } from "../json-ld";
import { Shell } from "../shell";
import { jobPostingJsonLd } from "../../lib/seo";
import { JobDetailView } from "./job-detail-view";

export function JobDetailPage({ locale, model, job = null, shellMode = "browse" }) {
  return (
    <>
      {job ? <JsonLd data={jobPostingJsonLd(job, locale)} /> : null}
      <Shell locale={locale} mode={shellMode} jobId={job?.id || model.jobId}>
        <JobDetailView locale={locale} model={model} />
      </Shell>
    </>
  );
}
