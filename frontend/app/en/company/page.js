import { CompanyForm } from "../../../components/company-form";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <CompanyForm locale="en" />;
}
