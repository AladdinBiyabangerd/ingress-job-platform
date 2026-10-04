import { MyApplications } from "../../components/my-applications";
import { privatePageMetadata } from "../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <MyApplications locale="az" />;
}
