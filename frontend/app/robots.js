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
  // Public marketing / job pages + /llms.txt (static). Same allow/disallow for AI bots.
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/llms.txt"],
        disallow,
      },
      ...AI_BOTS.map((userAgent) => ({
        userAgent,
        allow: ["/", "/llms.txt"],
        disallow,
      })),
    ],
    sitemap: `${siteOrigin()}/sitemap.xml`,
    host: siteOrigin().replace(/^https?:\/\//, ""),
  };
}
