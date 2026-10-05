import { COMPANY_SORTS, CompaniesPage } from "../../../components/companies";
import { getCompanies } from "../../../lib/server/jobs";
import { companiesMetadata } from "../../../lib/seo";

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return companiesMetadata("en");
}

function one(value) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function Page({ searchParams }) {
  const params = (await searchParams) || {};
  const q = String(one(params.q) || "").trim().slice(0, 100);
  const rawSort = String(one(params.sort) || "jobs");
  const sort = COMPANY_SORTS.includes(rawSort) ? rawSort : "jobs";
  const page = Math.min(10000, Math.max(1, Number.parseInt(String(one(params.page) || "1"), 10) || 1));
  let data = null;
  let error = false;
  try {
    data = await getCompanies(q, sort, page);
  } catch {
    error = true;
  }
  return <CompaniesPage locale="en" data={data} error={error} q={q} sort={sort} />;
}
