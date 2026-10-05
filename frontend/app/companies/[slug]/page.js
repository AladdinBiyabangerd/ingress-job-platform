import { notFound } from "next/navigation";
import { CompanyPage } from "../../../components/company-page";
import { getCompany } from "../../../lib/server/jobs";
import { companyMetadata } from "../../../lib/seo";

export const revalidate = 60;

function pageOf(params) {
  const raw = Array.isArray(params?.page) ? params.page[0] : params?.page;
  return Math.min(10000, Math.max(1, Number.parseInt(String(raw || "1"), 10) || 1));
}

function clean(slug) {
  return String(slug || "").toLowerCase().slice(0, 120);
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  let data = null;
  try {
    data = await getCompany(clean(slug), 1);
  } catch {
    return { robots: { index: false, follow: false } };
  }
  // Before streaming starts, so an unknown company is a real 404.
  if (!data) notFound();
  return companyMetadata("az", data.company);
}

export default async function Page({ params, searchParams }) {
  const { slug } = await params;
  const page = pageOf(await searchParams);
  let data = null;
  try {
    data = await getCompany(clean(slug), page);
  } catch {
    throw new Error("company api unavailable");
  }
  if (!data) notFound();
  return <CompanyPage locale="az" data={data} />;
}
