import { fetchJobs } from "../lib/api";
import { LOCALES, absoluteUrl, hreflangMap, localePath } from "../lib/seo";

export const dynamic = "force-dynamic";

function entry(path, { jobId, lastModified, priority = 0.7 } = {}) {
  return {
    url: absoluteUrl(path),
    lastModified: lastModified || new Date(),
    changeFrequency: jobId ? "daily" : "hourly",
    priority,
    alternates: {
      languages: hreflangMap(jobId ? { jobId } : {}),
    },
  };
}

export default async function sitemap() {
  const entries = LOCALES.map((locale) =>
    entry(localePath(locale), { priority: locale === "az" ? 1 : 0.9 }),
  );

  try {
    const jobs = await fetchJobs();
    for (const job of jobs) {
      const modified = job.created_at ? new Date(job.created_at) : new Date();
      for (const locale of LOCALES) {
        entries.push(
          entry(localePath(locale, { jobId: job.id }), {
            jobId: job.id,
            lastModified: Number.isNaN(modified.getTime()) ? new Date() : modified,
            priority: 0.8,
          }),
        );
      }
    }
  } catch {
    // Public sitemap still lists home locales when the jobs API is down.
  }

  return entries;
}
