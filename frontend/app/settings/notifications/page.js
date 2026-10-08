import { EmailSettings } from "../../../components/email-settings";
import { getEmailPrefs } from "../../../lib/server/email-prefs";
import { privatePageMetadata } from "../../../lib/seo";

export const metadata = privatePageMetadata;

export default async function Page() {
  const initial = await getEmailPrefs();
  return <EmailSettings locale="az" initialPrefs={initial.prefs} />;
}
