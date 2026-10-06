import { MeSkills } from "../../../components/me-skills";
import { getSkillBundle } from "../../../lib/server/skills";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getSkillBundle("az");
  return <MeSkills locale="az" initialRoles={initial.roles} initialGap={initial.gap} />;
}
