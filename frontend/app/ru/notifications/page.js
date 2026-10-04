import { NotificationsPage } from "../../../components/notifications-page";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default function Page() {
  return <NotificationsPage locale="ru" />;
}
