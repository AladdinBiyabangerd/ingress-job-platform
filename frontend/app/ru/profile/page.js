import { ProfileForm } from "../../../components/profile-form";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <ProfileForm locale="ru" />;
}
