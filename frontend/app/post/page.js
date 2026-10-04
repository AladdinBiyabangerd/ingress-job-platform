import { PostPage } from "../../components/post-page";
import { privatePageMetadata } from "../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <PostPage locale="az" />;
}
