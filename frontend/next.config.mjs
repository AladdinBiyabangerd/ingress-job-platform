/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      { source: "/settings/emails", destination: "/settings/notifications", permanent: true },
      { source: "/en/settings/emails", destination: "/en/settings/notifications", permanent: true },
      { source: "/ru/settings/emails", destination: "/ru/settings/notifications", permanent: true },
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
