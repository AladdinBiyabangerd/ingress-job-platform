import { MeSkills } from "../../../../components/me-skills";
import { getSkillBundle } from "../../../../lib/server/skills";
import { privatePageMetadata } from "../../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getSkillBundle("ru");
  return <MeSkills locale="ru" initialRoles={initial.roles} initialGap={initial.gap} />;
}
