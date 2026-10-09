import { headers } from "next/headers";
import "./globals.css";
import "@fontsource/plus-jakarta-sans/latin-400.css";
import "@fontsource/plus-jakarta-sans/latin-500.css";
import "@fontsource/plus-jakarta-sans/latin-600.css";
import "@fontsource/plus-jakarta-sans/latin-700.css";
import "@fontsource/plus-jakarta-sans/latin-ext-400.css";
import "@fontsource/plus-jakarta-sans/latin-ext-500.css";
import "@fontsource/plus-jakarta-sans/latin-ext-600.css";
import "@fontsource/plus-jakarta-sans/latin-ext-700.css";
import { MeSeed } from "../components/me-seed";
import { getMe } from "../lib/server/me";
import { SITE, homeMetadata, siteOrigin } from "../lib/seo";

const defaults = homeMetadata("az");

export const metadata = {
  metadataBase: new URL(siteOrigin()),
  title: {
    default: defaults.title,
    template: "%s",
  },
  description: defaults.description,
  applicationName: SITE.name,
  authors: [{ name: SITE.name }],
  creator: SITE.name,
  publisher: SITE.name,
  keywords: defaults.keywords,
  category: "jobs",
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    shortcut: ["/favicon.svg"],
    apple: [{ url: "/ingress-mark.svg" }],
  },
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    title: SITE.name,
    capable: true,
    statusBarStyle: "default",
  },
  other: {
    "geo.region": "AZ",
    "geo.placename": "Azerbaijan",
  },
};

export const viewport = {
  themeColor: SITE.themeColor,
  width: "device-width",
  initialScale: 1,
};

export default async function RootLayout({ children }) {
  const headerList = await headers();
  const locale = headerList.get("x-locale") || "az";
  const me = await getMe();
  return (
    <html lang={locale}>
      <body>
        <MeSeed me={me}>{children}</MeSeed>
      </body>
    </html>
  );
}
