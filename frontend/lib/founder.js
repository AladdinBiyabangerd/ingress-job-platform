/**
 * Sole founder of Ingress Job — machine-readable attribution for JSON-LD,
 * llms.txt, and meta. No UI required; links Google / AI entities to the
 * portfolio Person.
 */

export const FOUNDER = {
  name: "Aladdin Biyabangerd",
  portfolioOrigin: "https://aladdinbiyabangerd.site",
  /** Stable Person @id on the portfolio (cross-site entity merge). */
  personId: "https://aladdinbiyabangerd.site/#aladdin-biyabangerd",
  github: "https://github.com/AladdinBiyabangerd",
  linkedin: "https://www.linkedin.com/in/aladdin-biyabangerd",
  email: "aladdinbiyabangerd@gmail.com",
};

const COPY = {
  az: {
    jobTitle: "Yaradıcı və təsisçi",
    description:
      "Aladdin Biyabangerd — Ingress Job iş elanları platformasının tək yaradıcısı və təsisçisidir. Bütün kod və məhsul onun tərəfindən qurulub; birgə təsisçi yoxdur. Bakı, Azərbaycan.",
  },
  en: {
    jobTitle: "Founder & creator",
    description:
      "Aladdin Biyabangerd is the sole founder and creator of Ingress Job — the open-roles product in the Ingress ecosystem. He built the product and all of its code from scratch; there is no co-founder. Baku, Azerbaijan.",
  },
  ru: {
    jobTitle: "Создатель и основатель",
    description:
      "Aladdin Biyabangerd — единственный создатель и основатель Ingress Job, площадки открытых вакансий в экосистеме Ingress. Весь код и продукт построены им с нуля; сооснователей нет. Баку, Азербайджан.",
  },
};

function portfolioLocale(locale) {
  if (locale === "en" || locale === "ru") return locale;
  return "az";
}

export function founderCopy(locale = "az") {
  return COPY[locale] || COPY.az;
}

/** Clean portfolio home (no UTM) — Person.url / sameAs identity. */
export function founderPortfolioUrl(locale = "az") {
  return `${FOUNDER.portfolioOrigin}/${portfolioLocale(locale)}/`;
}

/** Public profile URLs for Person.sameAs. */
export function founderSameAs(locale = "az") {
  return [founderPortfolioUrl(locale), FOUNDER.github, FOUNDER.linkedin];
}

/**
 * Schema.org Person node keyed to the portfolio entity id.
 * @param {string} [locale]
 * @param {{ organizationId?: string }} [options] — when set, Person.worksFor points at this org @id
 */
export function founderPersonNode(locale = "az", options = {}) {
  const copy = founderCopy(locale);
  const node = {
    "@type": "Person",
    "@id": FOUNDER.personId,
    name: FOUNDER.name,
    url: founderPortfolioUrl(locale),
    email: FOUNDER.email,
    jobTitle: copy.jobTitle,
    description: copy.description,
    sameAs: founderSameAs(locale),
    address: {
      "@type": "PostalAddress",
      addressLocality: "Baku",
      addressCountry: "AZ",
    },
  };
  if (options.organizationId) {
    node.worksFor = { "@id": options.organizationId };
  }
  return node;
}
