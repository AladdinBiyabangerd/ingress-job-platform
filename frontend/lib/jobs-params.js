/** Build query string for GET /api/v1/jobs (and the Next BFF). */
export function jobsListParams({
  page = 1,
  perPage = 20,
  q = "",
  company = "",
  city = "",
  remote = false,
  relocation = false,
  onsite = false,
  when = "any",
  sort = "newest",
  languages = [],
  categories = [],
  stacks = [],
  salaryMin = "",
  salaryMax = "",
} = {}) {
  const params = new URLSearchParams();
  params.set("page", String(Math.max(1, Number(page) || 1)));
  params.set("per_page", String(Math.max(1, Math.min(60, Number(perPage) || 20))));
  const query = String(q || "").trim();
  if (query) params.set("q", query);
  const companyQ = String(company || "").trim();
  if (companyQ) params.set("company", companyQ);
  const cityQ = String(city || "").trim();
  if (cityQ) params.set("city", cityQ);
  if (remote) params.set("remote", "true");
  if (relocation) params.set("relocation", "true");
  if (onsite) params.set("onsite", "true");
  if (when && when !== "any") params.set("when", when);
  if (sort && sort !== "newest") params.set("sort", sort);
  for (const code of languages || []) {
    const value = String(code || "").trim();
    if (value) params.append("language", value);
  }
  for (const name of categories || []) {
    const value = String(name || "").trim();
    if (value) params.append("category", value);
  }
  for (const name of stacks || []) {
    const value = String(name || "").trim();
    if (value) params.append("stack", value);
  }
  const minRaw = String(salaryMin ?? "").trim();
  const maxRaw = String(salaryMax ?? "").trim();
  if (minRaw !== "" && Number.isFinite(Number(minRaw))) params.set("salary_min", String(Number(minRaw)));
  if (maxRaw !== "" && Number.isFinite(Number(maxRaw))) params.set("salary_max", String(Number(maxRaw)));
  return params;
}
