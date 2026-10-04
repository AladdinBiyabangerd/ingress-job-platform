import { headers } from "next/headers";
import "./globals.css";
import { Plus_Jakarta_Sans } from "next/font/google";
import { homeMetadata, siteOrigin } from "../lib/seo";

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
  applicationName: "ingress-job",
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
