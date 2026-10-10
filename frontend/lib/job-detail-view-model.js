import { hrefFor, text } from "./copy";
import { relativePosted } from "./dates";
import { descriptionBlocks } from "./description";

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

function normalizeHeading(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[:：]+$/u, "");
}

const ABOUT_KEYS = new Set(["about the role", "about", "rol haqqında", "о роли", "о вакансии"]);
const RESP_KEYS = new Set([
  "key responsibilities",
  "responsibilities",
  "əsas vəzifələr",
  "vəzifələr",
  "обязанности",
]);
const REQ_KEYS = new Set(["requirements", "tələblər", "требования"]);
const NICE_KEYS = new Set(["nice to have", "üstünlük", "будет плюсом", "желательно"]);
const BENEFIT_KEYS = new Set(["benefits", "imkanlar", "льготы", "что мы предлагаем"]);

function sectionKind(title) {
  const key = normalizeHeading(title);
  if (ABOUT_KEYS.has(key)) return "about";
  if (RESP_KEYS.has(key)) return "responsibilities";
  if (REQ_KEYS.has(key)) return "requirements";
  if (NICE_KEYS.has(key)) return "nice";
  if (BENEFIT_KEYS.has(key)) return "benefits";
  return "other";
}

/** Turn description blocks into titled sections for the detail layout. */
export function sectionsFromBlocks(blocks) {
  const sections = [];
  let current = null;

  function start(title, id) {
    current = { id, title, type: "prose", paragraphs: [], items: [] };
    sections.push(current);
  }

  for (const block of blocks || []) {
    if (block.type === "heading") {
      const kind = sectionKind(block.text);
      start(block.text, kind === "other" ? `sec-${sections.length}` : kind);
      continue;
    }
    if (!current) start("", `sec-${sections.length}`);
    if (block.type === "list") {
      current.type = "list";
      current.items.push(...(block.items || []));
    } else if (block.text) {
      if (current.type === "list" && current.items.length) {
        start("", `sec-${sections.length}`);
      }
      current.type = "prose";
      current.paragraphs.push(block.text);
    }
  }

  return sections.filter((sec) => sec.paragraphs.length || sec.items.length);
}

function benefitsFromSections(sections) {
  const benefit = (sections || []).find((sec) => sec.id === "benefits");
  if (!benefit || !benefit.items?.length) return [];
  if (benefit.items.some((item) => String(item).length > 80)) return [];
  return benefit.items.slice(0, 6).map((label, index) => ({
    id: `b-${index}`,
    label,
    icon: ["clock", "heart", "book", "globe", "shield", "star"][index % 6],
  }));
}

function firstIntro(blocks, sections) {
  const about = (sections || []).find((sec) => sec.id === "about");
  if (about?.paragraphs?.[0]) {
    const text = about.paragraphs[0].trim();
    if (text.length <= 220) return text;
    return `${text.slice(0, 200).trim()}…`;
  }
  const first = (blocks || []).find((b) => b.type !== "heading" && b.type !== "list" && b.text);
  if (!first?.text) return "";
  const text = first.text.trim();
  if (text.length <= 220) return text;
  return `${text.slice(0, 200).trim()}…`;
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
  const benefits = benefitsFromSections(sections);
  const displaySections = sections.filter((sec) => sec.id !== "benefits");

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
    hasOriginal: Boolean(job.has_original),
    form: job.form || null,
    returnTo: jobHref,
    companyPageLabel: Boolean(job.company_slug),
  };
}
