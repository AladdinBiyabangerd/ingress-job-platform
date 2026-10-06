import { NotificationsPage } from "../../../components/notifications-page";
import { getNotifications } from "../../../lib/server/notifications";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getNotifications();
  return (
    <NotificationsPage locale="en" initialItems={initial.items} initialUnread={initial.unread} />
  );
}
