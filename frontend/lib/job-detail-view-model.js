import { hrefFor, text } from "./copy";
import { relativePosted } from "./dates";
import { descriptionBlocks } from "./description";
import { benefitsFromSections, firstIntro, sectionsFromBlocks } from "./job-detail-sections";

export { sectionsFromBlocks } from "./job-detail-sections";

function companyInitial(name) {
  const s = String(name || "").trim();
  return s ? s.charAt(0).toUpperCase() : "?";
}

function jobTypeLabel(t, jobType) {
  if (jobType === "ofis") return t.jobOffice;
  if (jobType === "hibrid") return t.jobHybrid;
  if (jobType === "uzaqdan") return t.jobRemoteType;
  if (jobType === "full-time") return t.jdFullTime || "Full-time";
  return "";
}

/**
 * Map a public job API object (+ auth) into the shared Job Detail view model.
 * Omits rows when data is missing — never invents company size/industry/cover.
 */
export function jobToDetailViewModel({ locale, job, authState = "guest", companyExtra = null }) {
  const t = text(locale);
  const listingType = job.onsite ? "company_posted" : "external";
  const blocks = descriptionBlocks(job.text, job.title);
  const sections = sectionsFromBlocks(blocks);
  const companyName = job.company || t.noCompany;
  const jobHref = hrefFor(locale, { jobId: job.id });
  const place = job.remote
    ? job.city
      ? `${job.city}`
      : t.placeRemote
    : job.city || "";
  const jobType = jobTypeLabel(t, job.job_type);
  const posted = relativePosted(job.created_at, locale, {
    daysAgo: typeof t.jdDaysAgo === "function" ? t.jdDaysAgo : undefined,
    today: t.jdToday,
    yesterday: t.jdYesterday,
  });
  const postedLabel = posted
    ? posted.startsWith("Posted") || /əvvəl|назад|ago|сегодня|dünən|bu gün|yesterday|today/i.test(posted)
      ? /^(Posted|Yerləşdirilib|Опубликовано)/i.test(posted)
        ? posted
        : `${t.jdPostedPrefix || "Posted"} ${posted}`
      : `${t.jdPostedPrefix || "Posted"} ${posted}`
    : "";

  const meta = {
    location: place || null,
    remote: job.remote ? t.jdRemoteOk || t.placeRemote : null,
    relocation: job.relocation ? t.jdRelocationAvailable || t.relocationBadge : null,
    jobType: jobType || null,
    experience: null,
    languages: null,
    salary: job.salary || null,
    posted: postedLabel || null,
    postedDateTime: job.created_at || null,
  };

  const stack = Array.isArray(job.tech_stack) ? job.tech_stack.filter(Boolean) : [];
  const benefitSection = (sections || []).find((sec) => sec.id === "benefits");
  const benefits = benefitsFromSections(sections);
  const displaySections = benefits.length
    ? sections.filter((sec) => sec.id !== "benefits")
    : sections;

  return {
    preview: false,
    jobId: job.id,
    listingType,
    authState: authState === "signed_in" ? "signed_in" : "guest",
    title: job.title || "",
    intro: firstIntro(blocks, sections),
    company: {
      name: companyName,
      slug: job.company_slug || "",
      initial: companyInitial(companyName),
      about: companyExtra?.about || "",
      size: companyExtra?.size || null,
      industry: companyExtra?.industry || null,
      location: companyExtra?.location || job.city || null,
      cover: null,
      pageHref: job.company_slug ? hrefFor(locale, { companySlug: job.company_slug }) : "",
    },
    meta,
    skills: stack,
    sections: displaySections,
    benefits,
    benefitsTitle: benefitSection?.title || t.jdBenefits || "Benefits",
    hasOriginal: Boolean(job.has_original),
    form: job.form || null,
    returnTo: jobHref,
    companyPageLabel: Boolean(job.company_slug),
  };
}
