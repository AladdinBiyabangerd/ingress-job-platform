import "./globals.css";
import { Plus_Jakarta_Sans } from "next/font/google";

const sans = Plus_Jakarta_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
});

export const metadata = {
  title: "ingress-job",
  description: "Browse collected job listings.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="az" className={sans.className}>
      <body>{children}</body>
    </html>
  );
}
