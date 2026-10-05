import { UnsubscribePage } from "../../../components/unsubscribe-page";

export default function Page({ params }) {
  return <UnsubscribePage locale="az" token={params.token} />;
}
