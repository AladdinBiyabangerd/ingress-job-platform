import { headers } from "next/headers";
import "./globals.css";
import { Plus_Jakarta_Sans } from "next/font/google";
import { SITE, homeMetadata, siteOrigin } from "../lib/seo";

const sans = Plus_Jakarta_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
});

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
  return (
    <html lang={locale} className={sans.className}>
      <body>{children}</body>
    </html>
  );
}
