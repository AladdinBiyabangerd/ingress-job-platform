import { hrefFor } from "./copy";

export const LOCALES = ["az", "en", "ru"];

const HOME = {
  az: {
    title: "ingress-job — Açıq iş elanları",
    description:
      "Açıq iş elanlarına baxın. Başlıq və ya şirkət üzrə axtarın, şəhər və dilə görə süzün.",
  },
  en: {
    title: "ingress-job — Open roles",
    description:
      "Browse open job listings. Search by title or company and filter by city and language.",
  },
  ru: {
    title: "ingress-job — Открытые вакансии",
    description:
      "Смотрите открытые вакансии. Ищите по должности или компании, фильтруйте по городу и языку.",
  },
};

const OG_LOCALE = { az: "az_AZ", en: "en_US", ru: "ru_RU" };

export function siteOrigin() {
  const configured = (process.env.APP_URL || process.env.NEXT_PUBLIC_APP_URL || "").trim().replace(/\/$/, "");
  if (configured) return configured;
  const railwayHost = (process.env.RAILWAY_PUBLIC_DOMAIN || "").trim();
  if (railwayHost) return `https://${railwayHost}`;
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
    map[locale] = absoluteUrl(localePath(locale, { jobId }));
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

export function homeMetadata(locale = "az") {
  const copy = HOME[locale] || HOME.az;
  const path = localePath(locale);
  const url = absoluteUrl(path);
  const languages = hreflangMap();
  return {
    title: copy.title,
    description: copy.description,
    alternates: {
      canonical: url,
      languages,
    },
    openGraph: {
      type: "website",
      url,
      title: copy.title,
      description: copy.description,
      siteName: "ingress-job",
      locale: OG_LOCALE[locale] || OG_LOCALE.az,
      alternateLocale: LOCALES.filter((code) => code !== locale).map((code) => OG_LOCALE[code]),
    },
    twitter: {
      card: "summary",
      title: copy.title,
      description: copy.description,
    },
    robots: { index: true, follow: true },
  };
}

export function jobMetadata(locale, job) {
  if (!job) {
    return {
      title: "ingress-job",
      robots: { index: false, follow: false },
    };
  }
  const company = (job.company || "").trim();
  const place = job.remote ? "Remote" : (job.city || "").trim();
  const titleBits = [job.title, company].filter(Boolean);
  const title = `${titleBits.join(" — ")} | ingress-job`;
  const description = truncateText(
    [job.title, company, place, job.text].filter(Boolean).join(". "),
  );
  const path = localePath(locale, { jobId: job.id });
  const url = absoluteUrl(path);
  const languages = hreflangMap({ jobId: job.id });
  return {
    title,
    description,
    alternates: {
      canonical: url,
      languages,
    },
    openGraph: {
      type: "article",
      url,
      title,
      description,
      siteName: "ingress-job",
      locale: OG_LOCALE[locale] || OG_LOCALE.az,
      alternateLocale: LOCALES.filter((code) => code !== locale).map((code) => OG_LOCALE[code]),
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
    robots: { index: true, follow: true },
  };
}

export const privatePageMetadata = {
  robots: {
    index: false,
    follow: false,
    googleBot: { index: false, follow: false },
  },
};

export function jobPostingJsonLd(job, locale = "az") {
  const url = absoluteUrl(localePath(locale, { jobId: job.id }));
  const description = truncateText(job.text || job.title, 5000);
  const data = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description,
    datePosted: job.created_at || undefined,
    url,
    directApply: Boolean(job.onsite),
    hiringOrganization: {
      "@type": "Organization",
      name: job.company || "ingress-job",
    },
  };
  if (job.remote || job.job_type === "uzaqdan") {
    data.jobLocationType = "TELECOMMUTE";
  }
  if (job.city && !job.remote) {
    data.jobLocation = {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: job.city,
        addressCountry: "AZ",
      },
    };
  } else if (job.remote || job.job_type === "uzaqdan") {
    data.applicantLocationRequirements = {
      "@type": "Country",
      name: "AZ",
    };
  }
  return data;
}

export function jsonLdScript(data) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
