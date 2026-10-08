import { RecommendationJobs } from "../../../../../components/recommendations";
import { getRecommendationBundle } from "../../../../../lib/server/recommendations";
import { privatePageMetadata } from "../../../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page({ searchParams }) {
  const query = (await searchParams) || {};
  const role = String(query.role || "").trim();
  const initial = await getRecommendationBundle("en", role, false);
  return (
    <RecommendationJobs
      locale="en"
      initialRoles={initial.roles}
      initialMatches={initial.matches}
      initialRole={initial.role || role}
    />
  );
}
