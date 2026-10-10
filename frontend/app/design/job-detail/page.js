import { JobDetailPage } from "../../../components/job-detail/job-detail-page";
import { DETAIL_STATES, fixtureViewModel, parseDetailState } from "../../../lib/job-detail-fixtures";
import { text } from "../../../lib/copy";

export const dynamic = "force-dynamic";

const LABELS = {
  company_signed_in: "Company · signed in",
  company_guest: "Company · guest",
  external_signed_in: "External · signed in",
  external_guest: "External · guest",
};

export const metadata = {
  title: "Job Detail design preview — Ingress Job",
  robots: { index: false, follow: false },
};

export default async function DesignJobDetailPage({ searchParams }) {
  const locale = "en";
  const t = text(locale);
  const params = await searchParams;
  const state = parseDetailState(params?.state);
  const model = fixtureViewModel(state);

  return (
    <>
      <div className="jd-preview-bar">
        <strong>{t.jdPreviewStates}</strong>
        {DETAIL_STATES.map((key) => (
          <a key={key} href={`/design/job-detail?state=${key}`} className={key === state ? "is-active" : undefined}>
            {LABELS[key]}
          </a>
        ))}
        <span className="jd-preview-note">{t.jdPreviewNote}</span>
      </div>
      <JobDetailPage locale={locale} model={model} shellMode="browse" />
    </>
  );
}
