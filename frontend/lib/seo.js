import { hrefFor, text } from "./copy";

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
      "Azərbaycanda açıq iş elanlarına baxın. Başlıq və ya şirkət üzrə axtarın, şəhər və dilə görə süzün.",
    keywords: [
      "iş elanları",
      "vakansiya",
      "iş axtarışı",
      "Azərbaycan iş",
      "Bakı vakansiya",
      "Ingress Job",
    ],
    breadcrumbHome: "Elanlar",
    ogImageAlt: "Ingress Job — açıq iş elanları",
    countryName: "Azərbaycan",
    knowsAbout: ["iş elanları", "vakansiyalar", "işə qəbul", "Azərbaycan əmək bazarı"],
  },
  en: {
    title: "Ingress Job — Open roles",
    description:
      "Browse open job listings in Azerbaijan. Search by title or company and filter by city and language.",
    keywords: [
      "jobs Azerbaijan",
      "job listings",
      "vacancies Baku",
      "open roles",
      "Ingress Job",
    ],
    breadcrumbHome: "Jobs",
    ogImageAlt: "Ingress Job — open job listings",
    countryName: "Azerbaijan",
    knowsAbout: ["job listings", "vacancies", "hiring", "Azerbaijan job market"],
  },
  ru: {
    title: "Ingress Job — Открытые вакансии",
    description:
      "Смотрите открытые вакансии в Азербайджане. Ищите по должности или компании, фильтруйте по городу и языку.",
    keywords: [
      "вакансии Азербайджан",
      "работа Баку",
      "открытые вакансии",
      "поиск работы",
      "Ingress Job",
    ],
    breadcrumbHome: "Вакансии",
    ogImageAlt: "Ingress Job — открытые вакансии",
    countryName: "Азербайджан",
    knowsAbout: ["вакансии", "поиск работы", "найм", "рынок труда Азербайджана"],
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

export function localePath(locale, { jobId } = {}) {
  return hrefFor(locale, jobId ? { jobId } : {});
}

export function hreflangMap({ jobId } = {}) {
  const map = {};
  for (const locale of LOCALES) {
    map[HTML_LANG[locale]] = absoluteUrl(localePath(locale, { jobId }));
  }
  map["x-default"] = absoluteUrl(localePath("az", { jobId }));
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

function sharedMeta({ locale, title, description, path, jobId, type = "website", keywords }) {
  const url = absoluteUrl(path);
  const languages = hreflangMap(jobId ? { jobId } : {});
  const images = ogImages(locale);
  return {
    title,
    description,
    keywords: keywords?.length ? keywords : undefined,
    authors: [{ name: SITE.name }],
    creator: SITE.name,
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

export const privatePageMetadata = {
  robots: {
    index: false,
    follow: false,
    googleBot: { index: false, follow: false },
  },
};

function employmentType(job) {
  if (job.job_type === "uzaqdan" || job.remote) return "FULL_TIME";
  if (job.job_type === "hibrid") return "FULL_TIME";
  if (job.job_type === "ofis") return "FULL_TIME";
  return undefined;
}

function salaryJsonLd(salary) {
  const raw = String(salary || "").trim();
  if (!raw) return undefined;
  const match = raw.match(/(\d{2,7}(?:[.,\s]\d{3})*(?:[.,]\d+)?)/);
  if (!match) return undefined;
  const digits = match[1].replace(/[^\d.,]/g, "").replace(/\s/g, "");
  const normalized = digits.includes(",") && digits.includes(".")
    ? digits.replace(/,/g, "")
    : digits.replace(/,(?=\d{3}\b)/g, "").replace(",", ".");
  const value = Number(normalized.replace(/\.(?=\d{3}\b)/g, ""));
  if (!Number.isFinite(value) || value <= 0) return undefined;
  return {
    "@type": "MonetaryAmount",
    currency: "AZN",
    value: {
      "@type": "QuantitativeValue",
      value,
      unitText: "MONTH",
    },
  };
}

function organizationNode(locale) {
  const copy = homeCopy(locale);
  const origin = siteOrigin();
  return {
    "@type": "Organization",
    "@id": `${origin}/#organization`,
    name: SITE.name,
    url: origin,
    logo: {
      "@type": "ImageObject",
      url: absoluteUrl(SITE.logoPath),
    },
    description: copy.description,
    knowsAbout: copy.knowsAbout,
    areaServed: {
      "@type": "Country",
      name: copy.countryName,
    },
  };
}

export function homeJsonLd(locale = "az") {
  const copy = homeCopy(locale);
  const faq = text(locale).faq;
  const origin = siteOrigin();
  const pageUrl = absoluteUrl(localePath(locale));
  const graph = [
    organizationNode(locale),
    {
      "@type": "WebSite",
      "@id": `${origin}/#website`,
      name: SITE.name,
      url: origin,
      description: copy.description,
      publisher: { "@id": `${origin}/#organization` },
      inLanguage: HTML_LANG[locale],
    },
    {
      "@type": "CollectionPage",
      "@id": `${pageUrl}#webpage`,
      url: pageUrl,
      name: copy.title,
      description: copy.description,
      isPartOf: { "@id": `${origin}/#website` },
      about: { "@id": `${origin}/#organization` },
      inLanguage: HTML_LANG[locale],
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
      sameAs: origin,
    },
    mainEntityOfPage: { "@id": `${url}#webpage` },
  };
  const employment = employmentType(job);
  if (employment) posting.employmentType = employment;
  const salary = salaryJsonLd(job.salary);
  if (salary) posting.baseSalary = salary;
  if (job.remote || job.job_type === "uzaqdan") {
    posting.jobLocationType = "TELECOMMUTE";
    posting.applicantLocationRequirements = {
      "@type": "Country",
      name: "AZ",
    };
  }
  if (job.city && !job.remote) {
    posting.jobLocation = {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: job.city,
        addressCountry: "AZ",
      },
    };
  } else if (job.job_type === "hibrid" && job.city) {
    posting.jobLocation = {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: job.city,
        addressCountry: "AZ",
      },
    };
    posting.jobLocationType = "TELECOMMUTE";
  }

  return {
    "@context": "https://schema.org",
    "@graph": [
      organizationNode(locale),
      {
        "@type": "WebSite",
        "@id": `${origin}/#website`,
        name: SITE.name,
        url: origin,
        publisher: { "@id": `${origin}/#organization` },
        inLanguage: HTML_LANG[locale],
      },
      {
        "@type": "WebPage",
        "@id": `${url}#webpage`,
        url,
        name: `${job.title}${job.company ? ` — ${job.company}` : ""}`,
        description: truncateText(description),
        isPartOf: { "@id": `${origin}/#website` },
        mainEntity: { "@id": `${url}#job` },
        inLanguage: HTML_LANG[locale],
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: ui.breadcrumbHome || copy.breadcrumbHome,
            item: homeUrl,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: job.title,
            item: url,
          },
        ],
      },
      posting,
    ],
  };
}

export function jsonLdScript(data) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
