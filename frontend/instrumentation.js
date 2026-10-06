/** Prefer IPv6 so Node fetch can reach Railway private DNS (legacy IPv6-only). */
export async function register() {
  if (process.env.NEXT_RUNTIME === "edge") return;
  const dns = await import("node:dns");
  dns.setDefaultResultOrder("ipv6first");
}
