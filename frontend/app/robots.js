import { LOCALES, siteOrigin } from "../lib/seo";

const PRIVATE = ["admin", "applications", "saved", "talent", "profile", "notifications", "company", "post"];

/** Explicit AI crawler allow-list — same public rules as `*`. */
const AI_BOTS = [
  "GPTBot",
  "ChatGPT-User",
  "OAI-SearchBot",
  "PerplexityBot",
  "Google-Extended",
  "GoogleOther",
  "ClaudeBot",
  "anthropic-ai",
  "Applebot-Extended",
  "Bytespider",
  "CCBot",
];

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
  const disallow = privatePaths();
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow,
      },
      ...AI_BOTS.map((userAgent) => ({
        userAgent,
        allow: "/",
        disallow,
      })),
    ],
    sitemap: `${siteOrigin()}/sitemap.xml`,
    host: siteOrigin().replace(/^https?:\/\//, ""),
  };
}
