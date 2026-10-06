import { redirect } from "next/navigation";
import { CompanyForm } from "../../../components/company-form";
import { companyLoginPath, getCompanyProfile, isGuestMe } from "../../../lib/server/company";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getCompanyProfile();
  if (isGuestMe(initial.me)) redirect(companyLoginPath("ru"));
  return <CompanyForm locale="ru" initialMe={initial.me} initialProfile={initial.profile} />;
}
