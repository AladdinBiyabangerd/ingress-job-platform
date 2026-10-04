import { LOCALES, siteOrigin } from "../lib/seo";

const PRIVATE = ["admin", "applications", "profile", "notifications", "company", "post"];

function privatePaths() {
  const paths = ["/api/"];
  for (const segment of PRIVATE) {
    for (const locale of LOCALES) {
      paths.push(locale === "az" ? `/${segment}` : `/${locale}/${segment}`);
    }
  }
  return paths;
}

export default function robots() {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: privatePaths(),
    },
    sitemap: `${siteOrigin()}/sitemap.xml`,
  };
}
