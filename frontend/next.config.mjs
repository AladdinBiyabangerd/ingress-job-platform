/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      { source: "/settings/emails", destination: "/settings/notifications", permanent: true },
      { source: "/en/settings/emails", destination: "/en/settings/notifications", permanent: true },
      { source: "/ru/settings/emails", destination: "/ru/settings/notifications", permanent: true },
      // No index pages: /jobs lists on home, /me lives under /profile.
      { source: "/jobs", destination: "/", permanent: false },
      { source: "/en/jobs", destination: "/en", permanent: false },
      { source: "/ru/jobs", destination: "/ru", permanent: false },
      { source: "/me", destination: "/profile", permanent: false },
      { source: "/en/me", destination: "/en/profile", permanent: false },
      { source: "/ru/me", destination: "/ru/profile", permanent: false },
    ];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
    ];
  },
};
export default nextConfig;
