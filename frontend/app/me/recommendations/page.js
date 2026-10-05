import { Recommendations } from "../../../components/recommendations";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <Recommendations locale="az" />;
}
