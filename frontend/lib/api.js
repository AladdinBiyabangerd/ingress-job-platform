export function apiBase() {
  const direct = process.env.JOB_API_BASE_URL;
  if (direct) return direct.replace(/\/$/, "");
  const host = (process.env.API_PRIVATE_HOST || "").trim();
  if (host) {
    const port = process.env.API_PORT || "8080";
    return `http://${host}:${port}`;
  }
  return process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8010";
}

export async function fetchJobs() {
  const res = await fetch(`${apiBase()}/api/v1/jobs`, { cache: "no-store" });
  if (!res.ok) throw new Error(`jobs ${res.status}`);
  const data = await res.json();
  return Array.isArray(data.items) ? data.items : [];
}

export async function fetchJob(id) {
  const res = await fetch(`${apiBase()}/api/v1/jobs/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`job ${res.status}`);
  return res.json();
}
