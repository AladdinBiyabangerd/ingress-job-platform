import { fetchCompanies, fetchJobs, fetchTrends } from "../lib/api";
import { LOCALES, absoluteUrl, hreflangMap, localePath } from "../lib/seo";

export const revalidate = 60;

function entry(path, { route = {}, lastModified, changeFrequency = "hourly", priority = 0.7 } = {}) {
  return {
    url: absoluteUrl(path),
    lastModified: lastModified || new Date(),
    changeFrequency,
    priority,
    alternates: {
      languages: hreflangMap(route),
    },
  };
}

async function allJobSummaries() {
  const jobs = [];
  let page = 1;
  let pages = 1;
  do {
    const data = await fetchJobs({ page, perPage: 60, sort: "newest" });
    jobs.push(...(data.items || []));
    pages = Math.max(1, Number(data.pages) || 1);
    page += 1;
  } while (page <= pages);
  return jobs;
}

async function allCompanySummaries() {
  const companies = [];
  let page = 1;
  let pages = 1;
  do {
    const data = await fetchCompanies({ page, perPage: 60, sort: "jobs" });
    companies.push(...(data.items || []));
    pages = Math.max(1, Number(data.pages) || 1);
    page += 1;
  } while (page <= pages);
  return companies;
}

export default async function sitemap() {
  const entries = LOCALES.map((locale) =>
    entry(localePath(locale), { priority: locale === "az" ? 1 : 0.9 }),
  );

  for (const locale of LOCALES) {
    entries.push(
      entry(localePath(locale, { mode: "companies" }), {
        route: { mode: "companies" },
        priority: 0.7,
        changeFrequency: "daily",
      }),
    );
    entries.push(
      entry(localePath(locale, { mode: "trends" }), {
        route: { mode: "trends" },
        priority: 0.65,
        changeFrequency: "daily",
      }),
    );
  }

  try {
    const jobs = await allJobSummaries();
    for (const job of jobs) {
      const modified = job.created_at ? new Date(job.created_at) : new Date();
      for (const locale of LOCALES) {
        entries.push(
          entry(localePath(locale, { jobId: job.id }), {
            route: { jobId: job.id },
            lastModified: Number.isNaN(modified.getTime()) ? new Date() : modified,
            priority: 0.8,
            changeFrequency: "daily",
          }),
        );
      }
    }
  } catch {
    // Public sitemap still lists hubs when the jobs API is down.
  }

  try {
    const companies = await allCompanySummaries();
    for (const company of companies) {
      if (!company?.slug) continue;
      const modified = company.latest_posted ? new Date(company.latest_posted) : new Date();
      for (const locale of LOCALES) {
        entries.push(
          entry(localePath(locale, { companySlug: company.slug }), {
            route: { companySlug: company.slug },
            lastModified: Number.isNaN(modified.getTime()) ? new Date() : modified,
            priority: 0.6,
            changeFrequency: "daily",
          }),
        );
      }
    }
  } catch {
    // Company hubs remain listed above.
  }

  try {
    const trends = await fetchTrends({ lang: "az", limit: 40, windowDays: 7 });
    const skills = Array.isArray(trends?.items) ? trends.items : Array.isArray(trends) ? trends : [];
    for (const skill of skills) {
      const skillId = skill?.skill_id;
      if (skillId == null) continue;
      for (const locale of LOCALES) {
        entries.push(
          entry(localePath(locale, { mode: "trend", skillId }), {
            route: { mode: "trend", skillId },
            priority: 0.55,
            changeFrequency: "daily",
          }),
        );
      }
    }
  } catch {
    // Trends hub remains listed above.
  }

  return entries;
}
