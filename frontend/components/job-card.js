/** On-site application count for a job; null when applying happens on the source site. */
export function applicationsLabel(t, job, { short = false } = {}) {
  if (!job.onsite || typeof job.applications !== "number") return null;
  if (job.applications > 0) return t.applicationsCount(job.applications);
  return short ? t.applicationsFirst : t.applicationsNone;
}

/** Unique candidates who opened the original listing; null when the job has no source URL. */
export function originalOpensLabel(t, job, { short = false } = {}) {
  if (!job?.has_original || typeof job.original_opens !== "number") return null;
  if (job.original_opens > 0) {
    return t.originalOpensCount
      ? t.originalOpensCount(job.original_opens)
      : String(job.original_opens);
  }
  return short
    ? t.originalOpensFirst || t.applicationsFirst
    : t.originalOpensNone || t.applicationsNone;
}
