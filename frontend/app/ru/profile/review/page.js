import { ProfileReview } from "../../../../components/profile-review";
import { getProfileReview } from "../../../../lib/server/profile-review";
import { privatePageMetadata } from "../../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getProfileReview("ru");
  return <ProfileReview locale="ru" initialProfile={initial.profile} initialRoles={initial.roles} />;
}
