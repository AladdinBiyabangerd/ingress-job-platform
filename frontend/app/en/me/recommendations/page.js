import { Recommendations } from "../../../../components/recommendations";
import { getRecommendationBundle } from "../../../../lib/server/recommendations";
import { privatePageMetadata } from "../../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getRecommendationBundle("en");
  return (
    <Recommendations locale="en" initialRoles={initial.roles} initialMatches={initial.matches} />
  );
}
