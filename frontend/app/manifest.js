import { SITE, siteOrigin } from "../lib/seo";

export default function manifest() {
  return {
    name: SITE.name,
    short_name: SITE.name,
    description: "Open job listings in Azerbaijan.",
    start_url: "/",
    display: "standalone",
    background_color: SITE.backgroundColor,
    theme_color: SITE.themeColor,
    lang: "az",
    id: siteOrigin(),
    icons: [
      {
        src: "/ingress-mark.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
