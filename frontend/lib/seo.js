import { hrefFor, text } from "./copy.js";
import { FOUNDER, founderPersonNode } from "./founder.js";
import { INGRESS, ingressUrl } from "./ingress.js";
import { salaryJsonLd } from "./salary.js";

export const LOCALES = ["az", "en", "ru"];
export const HTML_LANG = { az: "az", en: "en", ru: "ru" };
const OG_LOCALE = { az: "az_AZ", en: "en_US", ru: "ru_RU" };

export const SITE = {
  name: "Ingress Job",
  themeColor: "#001FFF",
  backgroundColor: "#f6f5f1",
  logoPath: "/ingress-mark.svg",
  ogImage: {
    path: "/opengraph-image",
    width: 1200,
    height: 630,
    type: "image/png",
  },
};

const HOME = {
  az: {
    title: "Ingress Job — Açıq iş elanları",
    description:
      "Ingress ekosisteminin iş elanları platforması. Azərbaycanda açıq vakansiyalara baxın; başlıq, şirkət, şəhər və dilə görə süzün.",
    keywords: [
      "iş elanları",
      "vakansiya",
      "iş axtarışı",
      "Azərbaycan iş",
      "Bakı vakansiya",
      "Bakı iş elanları",
      "IT vakansiya Azərbaycan",
      "remote iş",
      "iş elanları onlayn",
      "Ingress Job",
      "Ingress",
      "Ingress Academy",
      "Aladdin Biyabangerd",
    ],
    breadcrumbHome: "Elanlar",
    ogImageAlt: "Ingress Job — açıq iş elanları",
    countryName: "Azərbaycan",
    knowsAbout: ["iş elanları", "vakansiyalar", "işə qəbul", "Azərbaycan əmək bazarı", "Ingress ekosistemi"],
  },
  en: {
    title: "Ingress Job — Open roles",
    description:
      "The job board in the Ingress ecosystem. Browse open roles in Azerbaijan; search by title or company and filter by city and language.",
    keywords: [
      "jobs Azerbaijan",
      "job listings",
      "vacancies Baku",
      "open roles",
      "IT jobs Azerbaijan",
      "remote jobs Azerbaijan",
      "Baku tech jobs",
      "job board Azerbaijan",
      "Ingress Job",
      "Ingress",
      "Ingress Academy",
      "Aladdin Biyabangerd",
    ],
    breadcrumbHome: "Jobs",
    ogImageAlt: "Ingress Job — open job listings",
    countryName: "Azerbaijan",
    knowsAbout: ["job listings", "vacancies", "hiring", "Azerbaijan job market", "Ingress ecosystem"],
  },
  ru: {
    title: "Ingress Job — Открытые вакансии",
    description:
      "Площадка вакансий в экосистеме Ingress. Смотрите открытые вакансии в Азербайджане; ищите по должности или компании, фильтруйте по городу и языку.",
    keywords: [
      "вакансии Азербайджан",
      "работа Баку",
      "открытые вакансии",
      "поиск работы",
      "IT вакансии Баку",
      "удалённая работа Азербайджан",
      "доска вакансий",
      "Ingress Job",
      "Ingress",
      "Ingress Academy",
      "Aladdin Biyabangerd",
    ],
    breadcrumbHome: "Вакансии",
    ogImageAlt: "Ingress Job — открытые вакансии",
    countryName: "Азербайджан",
    knowsAbout: ["вакансии", "поиск работы", "найм", "рынок труда Азербайджана", "экосистема Ingress"],
  },
};

const INDEX_ROBOTS = {
  index: true,
  follow: true,
  googleBot: {
    index: true,
    follow: true,
    "max-image-preview": "large",
    "max-snippet": -1,
    "max-video-preview": -1,
  },
};

function homeCopy(locale = "az") {
  return HOME[locale] || HOME.az;
}

function apexOrigin(value) {
  try {
    const parsed = new URL(value.includes("://") ? value : `https://${value}`);
    if (parsed.hostname.startsWith("www.")) parsed.hostname = parsed.hostname.slice(4);
    return parsed.origin.replace(/\/$/, "");
  } catch {
    return value.replace(/\/$/, "");
  }
}

export function siteOrigin() {
  const configured = (process.env.APP_URL || process.env.NEXT_PUBLIC_APP_URL || "").trim();
  if (configured) return apexOrigin(configured);
  const railwayHost = (process.env.RAILWAY_PUBLIC_DOMAIN || "").trim();
  if (railwayHost) return apexOrigin(`https://${railwayHost}`);
  return "http://localhost:3010";
}

export function absoluteUrl(path = "/") {
  const origin = siteOrigin();
  if (!path || path === "/") return `${origin}/`;
  return `${origin}${path.startsWith("/") ? path : `/${path}`}`;
}

export function localePath(locale, { jobId, mode, companySlug, skillId } = {}) {
  if (jobId) return hrefFor(locale, { jobId });
  if (companySlug) return hrefFor(locale, { companySlug });
  if (skillId != null && String(skillId).trim() !== "") {
    return hrefFor(locale, { mode: mode || "trend", skillId });
  }
  return hrefFor(locale, mode ? { mode } : {});
}

export function hreflangMap(route = {}) {
  const map = {};
  for (const locale of LOCALES) {
    map[HTML_LANG[locale]] = absoluteUrl(localePath(locale, route));
  }
  map["x-default"] = absoluteUrl(localePath("az", route));
  return map;
}

export function truncateText(value, max = 160) {
  const text = String(value || "")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}

function ogImages(locale) {
  const copy = homeCopy(locale);
  return [
    {
      url: absoluteUrl(SITE.ogImage.path),
      width: SITE.ogImage.width,
      height: SITE.ogImage.height,
      alt: copy.ogImageAlt,
      type: SITE.ogImage.type,
    },
  ];
}

function sharedMeta({ locale, title, description, path, jobId, route, type = "website", keywords }) {
  const url = absoluteUrl(path);
  const languages = hreflangMap(route || (jobId ? { jobId } : {}));
  const images = ogImages(locale);
  return {
    title,
    description,
    keywords: keywords?.length ? keywords : undefined,
    authors: [
      { name: FOUNDER.name, url: FOUNDER.portfolioOrigin },
      { name: SITE.name },
    ],
    creator: FOUNDER.name,
    publisher: SITE.name,
    applicationName: SITE.name,
    alternates: {
      canonical: url,
      languages,
    },
    openGraph: {
      type,
      url,
      title,
      description,
      siteName: SITE.name,
      locale: OG_LOCALE[locale] || OG_LOCALE.az,
      alternateLocale: LOCALES.filter((code) => code !== locale).map((code) => OG_LOCALE[code]),
      images,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: images.map((image) => image.url),
    },
    robots: INDEX_ROBOTS,
    other: {
      "geo.region": "AZ",
      "geo.placename": homeCopy(locale).countryName,
    },
  };
}

export function homeMetadata(locale = "az") {
  const copy = homeCopy(locale);
  return sharedMeta({
    locale,
    title: copy.title,
    description: copy.description,
    path: localePath(locale),
    keywords: copy.keywords,
  });
}

export function jobMetadata(locale, job) {
  if (!job) {
    return {
      title: SITE.name,
      robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
    };
  }
  const company = (job.company || "").trim();
  const place = job.remote ? "Remote" : (job.city || "").trim();
  const titleBits = [job.title, company].filter(Boolean);
  const title = `${titleBits.join(" — ")} | ${SITE.name}`;
  const description = truncateText(
    [job.title, company, place, job.text].filter(Boolean).join(". "),
  );
  return sharedMeta({
    locale,
    title,
    description,
    path: localePath(locale, { jobId: job.id }),
    jobId: job.id,
    type: "article",
    keywords: [job.title, company, place, SITE.name].filter(Boolean),
  });
}

const COMPANIES_COPY = {
  az: {
    title: "Şirkətlər — açıq vakansiyalar və müraciətlər",
    description:
      "Ingress Job-da açıq elanı olan şirkətlər: elan sayı, texnologiyalar, uzaqdan iş və müraciət statistikası. Aladdin Biyabangerd tərəfindən qurulub.",
    breadcrumb: "Şirkətlər",
    company: (name, jobs) => `${name} — ${jobs} açıq elan`,
    keywords: ["şirkətlər", "işəgötürənlər", "vakansiya şirkətləri", "Ingress Job", "Aladdin Biyabangerd"],
  },
  en: {
    title: "Companies — open jobs and applications",
    description:
      "Companies hiring on Ingress Job: open roles, tech stack, remote work and application stats. Built by Aladdin Biyabangerd.",
    breadcrumb: "Companies",
    company: (name, jobs) => `${name} — ${jobs} open ${jobs === 1 ? "job" : "jobs"}`,
    keywords: ["companies hiring", "employers Azerbaijan", "job board companies", "Ingress Job", "Aladdin Biyabangerd"],
  },
  ru: {
    title: "Компании — открытые вакансии и отклики",
    description:
      "Компании с вакансиями на Ingress Job: количество вакансий, технологии, удалёнка и статистика откликов. Создано Aladdin Biyabangerd.",
    breadcrumb: "Компании",
    company: (name, jobs) => `${name} — открытые вакансии: ${jobs}`,
    keywords: ["компании", "работодатели", "вакансии компаний", "Ingress Job", "Aladdin Biyabangerd"],
  },
};

export function companiesMetadata(locale = "az") {
  const copy = COMPANIES_COPY[locale] || COMPANIES_COPY.az;
  return sharedMeta({
    locale,
    title: `${copy.title} | ${SITE.name}`,
    description: copy.description,
    path: localePath(locale, { mode: "companies" }),
    route: { mode: "companies" },
    keywords: copy.keywords,
  });
}

const TRENDS_COPY = {
  az: {
    title: "Bacarıq trendləri",
    description:
      "Ingress Job-un izlədiyi elanlarda bacarıq tələbinin payı və həftəlik dəyişimi. Bütün bazarı əks etdirmir.",
    breadcrumb: "Trendlər",
    skillTitle: (name) => `${name} — bacarıq trendi`,
    skillDescription: (name) =>
      `${name} bacarığının Ingress Job elanlarındakı tələb payı və həftəlik dəyişimi. Bütün bazarı əks etdirmir.`,
    skillJobsTitle: (name) => `${name} — tələb edən iş elanları`,
    skillJobsDescription: (name) =>
      `${name} bacarığı tələb olunan açıq elanlar Ingress Job-da. Trend səhifəsi tələb payını göstərir.`,
    keywords: ["bacarıq trendləri", "IT skills", "vakansiya tələbi", "Ingress Job", "Aladdin Biyabangerd"],
  },
  en: {
    title: "Skill trends",
    description:
      "Skill demand share and week-over-week change in listings Ingress Job tracks — not the whole market.",
    breadcrumb: "Trends",
    skillTitle: (name) => `${name} — skill trend`,
    skillDescription: (name) =>
      `Demand share and week-over-week change for ${name} in listings Ingress Job tracks — not the whole market.`,
    skillJobsTitle: (name) => `${name} — jobs requiring this skill`,
    skillJobsDescription: (name) =>
      `Open roles on Ingress Job that ask for ${name}. The trend page shows demand share over time.`,
    keywords: ["skill trends", "IT skills demand", "job market skills", "Ingress Job", "Aladdin Biyabangerd"],
  },
  ru: {
    title: "Тренды навыков",
    description:
      "Доля спроса на навыки и недельное изменение в вакансиях, которые отслеживает Ingress Job — не весь рынок.",
    breadcrumb: "Тренды",
    skillTitle: (name) => `${name} — тренд навыка`,
    skillDescription: (name) =>
      `Доля спроса и недельное изменение для ${name} в вакансиях Ingress Job — не весь рынок.`,
    skillJobsTitle: (name) => `${name} — вакансии с этим навыком`,
    skillJobsDescription: (name) =>
      `Открытые вакансии на Ingress Job, где требуется ${name}. Страница тренда показывает долю спроса.`,
    keywords: ["тренды навыков", "спрос на навыки", "IT навыки", "Ingress Job", "Aladdin Biyabangerd"],
  },
};

export function trendsMetadata(locale = "az") {
  const copy = TRENDS_COPY[locale] || TRENDS_COPY.az;
  return sharedMeta({
    locale,
    title: `${copy.title} | ${SITE.name}`,
    description: copy.description,
    path: localePath(locale, { mode: "trends" }),
    route: { mode: "trends" },
    keywords: copy.keywords,
  });
}

export function trendSkillMetadata(locale, skill, { jobs = false } = {}) {
  if (!skill?.name || skill.skill_id == null) {
    return { title: SITE.name, robots: { index: false, follow: false, googleBot: { index: false, follow: false } } };
  }
  const copy = TRENDS_COPY[locale] || TRENDS_COPY.az;
  const name = String(skill.name).trim();
  const mode = jobs ? "trendJobs" : "trend";
  return sharedMeta({
    locale,
    title: `${(jobs ? copy.skillJobsTitle : copy.skillTitle)(name)} | ${SITE.name}`,
    description: truncateText((jobs ? copy.skillJobsDescription : copy.skillDescription)(name)),
    path: localePath(locale, { mode, skillId: skill.skill_id }),
    route: { mode, skillId: skill.skill_id },
    keywords: [name, SITE.name, FOUNDER.name, ...(copy.keywords || [])].filter(Boolean),
  });
}

export function companyMetadata(locale, company) {
  if (!company) {
    return { title: SITE.name, robots: { index: false, follow: false, googleBot: { index: false, follow: false } } };
  }
  const copy = COMPANIES_COPY[locale] || COMPANIES_COPY.az;
  const tech = (company.top_tech || []).slice(0, 5).map((item) => item.name).filter(Boolean);
  const bits = [
    copy.company(company.name, company.open_jobs),
    (company.locations || []).slice(0, 3).join(", "),
    tech.join(", "),
  ].filter(Boolean);
  return sharedMeta({
    locale,
    title: `${copy.company(company.name, company.open_jobs)} | ${SITE.name}`,
    description: truncateText(bits.join(". ")),
    path: localePath(locale, { companySlug: company.slug }),
    route: { companySlug: company.slug },
    keywords: [company.name, ...tech, SITE.name, FOUNDER.name].filter(Boolean),
  });
}

export const privatePageMetadata = {
  robots: {
    index: false,
    follow: false,
    googleBot: { index: false, follow: false },
  },
};

/** Days after datePosted before the JobPosting is treated as expired for Google Jobs. */
const JOB_VALID_DAYS = 30;

function isHybrid(job) {
  return job.job_type === "hibrid";
}

/** Fully remote only — Google TELECOMMUTE must not be used for hybrid roles. */
function isFullyRemote(job) {
  if (isHybrid(job)) return false;
  return Boolean(job.remote) || job.job_type === "uzaqdan";
}

function placeFromCity(city) {
  const address = {
    "@type": "PostalAddress",
    addressCountry: "AZ",
  };
  const locality = String(city || "").trim();
  if (locality) address.addressLocality = locality;
  return {
    "@type": "Place",
    address,
  };
}

function applyJobLocation(posting, job) {
  const city = String(job.city || "").trim();
  if (isFullyRemote(job)) {
    posting.jobLocationType = "TELECOMMUTE";
    posting.applicantLocationRequirements = {
      "@type": "Country",
      name: "AZ",
    };
    if (city) posting.jobLocation = placeFromCity(city);
    return;
  }
  // Office / hybrid / unknown: physical Place only (country fallback if no city).
  posting.jobLocation = placeFromCity(city);
}

function validThroughFromPosted(datePosted) {
  const posted = Date.parse(datePosted || "");
  if (!Number.isFinite(posted)) return undefined;
  const through = new Date(posted);
  through.setUTCDate(through.getUTCDate() + JOB_VALID_DAYS);
  return through.toISOString();
}

function organizationNode(locale) {
  const copy = homeCopy(locale);
  const origin = siteOrigin();
  const parentUrl = ingressUrl(locale);
  return {
    "@type": "Organization",
    "@id": `${origin}/#organization`,
    name: SITE.name,
    url: origin,
    logo: {
      "@type": "ImageObject",
      url: absoluteUrl(SITE.logoPath),
    },
    email: FOUNDER.email,
    description: copy.description,
    founder: { "@id": FOUNDER.personId },
    knowsAbout: copy.knowsAbout,
    areaServed: {
      "@type": "Country",
      name: copy.countryName,
    },
    sameAs: [INGRESS.url, FOUNDER.portfolioOrigin],
    contactPoint: {
      "@type": "ContactPoint",
      email: FOUNDER.email,
      contactType: "founder",
      availableLanguage: LOCALES.map((code) => HTML_LANG[code]),
    },
    parentOrganization: {
      "@type": "Organization",
      name: INGRESS.name,
      url: parentUrl,
      sameAs: [INGRESS.url],
    },
  };
}

function websiteNode(locale) {
  const copy = homeCopy(locale);
  const origin = siteOrigin();
  const orgId = `${origin}/#organization`;
  const homeUrl = absoluteUrl(localePath(locale));
  return {
    "@type": "WebSite",
    "@id": `${origin}/#website`,
    name: SITE.name,
    url: origin,
    description: copy.description,
    publisher: { "@id": orgId },
    creator: { "@id": FOUNDER.personId },
    inLanguage: HTML_LANG[locale],
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${homeUrl}${homeUrl.includes("?") ? "&" : "?"}q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };
}

function coreEntityGraph(locale) {
  const origin = siteOrigin();
  const orgId = `${origin}/#organization`;
  return [
    organizationNode(locale),
    founderPersonNode(locale, { organizationId: orgId }),
    websiteNode(locale),
  ];
}

function breadcrumbList(items) {
  return {
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

export function homeJsonLd(locale = "az") {
  const copy = homeCopy(locale);
  const faq = text(locale).faq;
  const origin = siteOrigin();
  const pageUrl = absoluteUrl(localePath(locale));
  const orgId = `${origin}/#organization`;
  const graph = [
    ...coreEntityGraph(locale),
    {
      "@type": "CollectionPage",
      "@id": `${pageUrl}#webpage`,
      url: pageUrl,
      name: copy.title,
      description: copy.description,
      isPartOf: { "@id": `${origin}/#website` },
      about: { "@id": orgId },
      inLanguage: HTML_LANG[locale],
      author: { "@id": FOUNDER.personId },
    },
  ];
  if (faq?.items?.length) {
    graph.push({
      "@type": "FAQPage",
      "@id": `${pageUrl}#faq`,
      mainEntity: faq.items.map((item) => ({
        "@type": "Question",
        name: item.q,
        acceptedAnswer: {
          "@type": "Answer",
          text: item.a,
        },
      })),
    });
  }
  return {
    "@context": "https://schema.org",
    "@graph": graph,
  };
}

export function companiesJsonLd(locale = "az") {
  const home = homeCopy(locale);
  const copy = COMPANIES_COPY[locale] || COMPANIES_COPY.az;
  const origin = siteOrigin();
  const pageUrl = absoluteUrl(localePath(locale, { mode: "companies" }));
  const homeUrl = absoluteUrl(localePath(locale));
  return {
    "@context": "https://schema.org",
    "@graph": [
      ...coreEntityGraph(locale),
      {
        "@type": "CollectionPage",
        "@id": `${pageUrl}#webpage`,
        url: pageUrl,
        name: `${copy.title} | ${SITE.name}`,
        description: copy.description,
        isPartOf: { "@id": `${origin}/#website` },
        about: { "@id": `${origin}/#organization` },
        inLanguage: HTML_LANG[locale],
        author: { "@id": FOUNDER.personId },
      },
      breadcrumbList([
        { name: home.breadcrumbHome, url: homeUrl },
        { name: copy.breadcrumb, url: pageUrl },
      ]),
    ],
  };
}

export function companyJsonLd(locale, company) {
  if (!company) return null;
  const home = homeCopy(locale);
  const copy = COMPANIES_COPY[locale] || COMPANIES_COPY.az;
  const origin = siteOrigin();
  const pageUrl = absoluteUrl(localePath(locale, { companySlug: company.slug }));
  const homeUrl = absoluteUrl(localePath(locale));
  const companiesUrl = absoluteUrl(localePath(locale, { mode: "companies" }));
  const tech = (company.top_tech || []).slice(0, 8).map((item) => item.name).filter(Boolean);
  const hiringOrg = {
    "@type": "Organization",
    "@id": `${pageUrl}#employer`,
    name: company.name,
    url: pageUrl,
  };
  if (tech.length) hiringOrg.knowsAbout = tech;
  if ((company.locations || []).length) {
    hiringOrg.areaServed = company.locations.slice(0, 5).map((place) => ({
      "@type": "Place",
      name: place,
    }));
  }
  return {
    "@context": "https://schema.org",
    "@graph": [
      ...coreEntityGraph(locale),
      {
        "@type": "ProfilePage",
        "@id": `${pageUrl}#webpage`,
        url: pageUrl,
        name: `${copy.company(company.name, company.open_jobs)} | ${SITE.name}`,
        description: truncateText(
          [copy.company(company.name, company.open_jobs), tech.join(", ")].filter(Boolean).join(". "),
        ),
        isPartOf: { "@id": `${origin}/#website` },
        mainEntity: { "@id": hiringOrg["@id"] },
        inLanguage: HTML_LANG[locale],
      },
      hiringOrg,
      breadcrumbList([
        { name: home.breadcrumbHome, url: homeUrl },
        { name: copy.breadcrumb, url: companiesUrl },
        { name: company.name, url: pageUrl },
      ]),
    ],
  };
}

export function trendsJsonLd(locale = "az") {
  const home = homeCopy(locale);
  const copy = TRENDS_COPY[locale] || TRENDS_COPY.az;
  const origin = siteOrigin();
  const pageUrl = absoluteUrl(localePath(locale, { mode: "trends" }));
  const homeUrl = absoluteUrl(localePath(locale));
  return {
    "@context": "https://schema.org",
    "@graph": [
      ...coreEntityGraph(locale),
      {
        "@type": "CollectionPage",
        "@id": `${pageUrl}#webpage`,
        url: pageUrl,
        name: `${copy.title} | ${SITE.name}`,
        description: copy.description,
        isPartOf: { "@id": `${origin}/#website` },
        about: { "@id": `${origin}/#organization` },
        inLanguage: HTML_LANG[locale],
        author: { "@id": FOUNDER.personId },
      },
      breadcrumbList([
        { name: home.breadcrumbHome, url: homeUrl },
        { name: copy.breadcrumb, url: pageUrl },
      ]),
    ],
  };
}

export function trendSkillJsonLd(locale, skill) {
  if (!skill?.name || skill.skill_id == null) return null;
  const home = homeCopy(locale);
  const copy = TRENDS_COPY[locale] || TRENDS_COPY.az;
  const origin = siteOrigin();
  const name = String(skill.name).trim();
  const pageUrl = absoluteUrl(localePath(locale, { mode: "trend", skillId: skill.skill_id }));
  const homeUrl = absoluteUrl(localePath(locale));
  const trendsUrl = absoluteUrl(localePath(locale, { mode: "trends" }));
  return {
    "@context": "https://schema.org",
    "@graph": [
      ...coreEntityGraph(locale),
      {
        "@type": "WebPage",
        "@id": `${pageUrl}#webpage`,
        url: pageUrl,
        name: `${copy.skillTitle(name)} | ${SITE.name}`,
        description: truncateText(copy.skillDescription(name)),
        isPartOf: { "@id": `${origin}/#website` },
        about: {
          "@type": "Thing",
          name,
        },
        inLanguage: HTML_LANG[locale],
        author: { "@id": FOUNDER.personId },
      },
      breadcrumbList([
        { name: home.breadcrumbHome, url: homeUrl },
        { name: copy.breadcrumb, url: trendsUrl },
        { name, url: pageUrl },
      ]),
    ],
  };
}

export function jobPostingJsonLd(job, locale = "az") {
  const copy = homeCopy(locale);
  const ui = text(locale);
  const origin = siteOrigin();
  const homeUrl = absoluteUrl(localePath(locale));
  const url = absoluteUrl(localePath(locale, { jobId: job.id }));
  const description = truncateText(job.text || job.title, 5000);
  const posting = {
    "@type": "JobPosting",
    "@id": `${url}#job`,
    title: job.title,
    description,
    datePosted: job.created_at || undefined,
    url,
    directApply: Boolean(job.onsite),
    identifier: {
      "@type": "PropertyValue",
      name: SITE.name,
      value: String(job.id),
    },
    hiringOrganization: {
      "@type": "Organization",
      name: job.company || SITE.name,
    },
    mainEntityOfPage: { "@id": `${url}#webpage` },
  };
  const salary = salaryJsonLd(job.salary);
  if (salary) posting.baseSalary = salary;
  const validThrough = validThroughFromPosted(job.created_at);
  if (validThrough) posting.validThrough = validThrough;
  applyJobLocation(posting, job);

  return {
    "@context": "https://schema.org",
    "@graph": [
      ...coreEntityGraph(locale),
      {
        "@type": "WebPage",
        "@id": `${url}#webpage`,
        url,
        name: `${job.title}${job.company ? ` — ${job.company}` : ""}`,
        description: truncateText(description),
        isPartOf: { "@id": `${origin}/#website` },
        mainEntity: { "@id": `${url}#job` },
        inLanguage: HTML_LANG[locale],
        author: { "@id": FOUNDER.personId },
      },
      breadcrumbList([
        { name: ui.breadcrumbHome || copy.breadcrumbHome, url: homeUrl },
        { name: job.title, url },
      ]),
      posting,
    ],
  };
}

export function jsonLdScript(data) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
