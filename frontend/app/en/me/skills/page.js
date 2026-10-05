import { MeSkills } from "../../../../components/me-skills";
import { privatePageMetadata } from "../../../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <MeSkills locale="en" />;
}
