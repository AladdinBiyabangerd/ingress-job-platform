import { ProfileReview } from "../../../components/profile-review";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <ProfileReview locale="az" />;
}
