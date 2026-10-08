/** On-site application count for a job; null when applying happens on the source site. */
export function applicationsLabel(t, job, { short = false } = {}) {
  if (!job.onsite || typeof job.applications !== "number") return null;
  if (job.applications > 0) return t.applicationsCount(job.applications);
  return short ? t.applicationsFirst : t.applicationsNone;
}
