import { AdminPage } from "../../../components/admin-page";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <AdminPage locale="ru" />;
}
