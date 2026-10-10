import { text } from "../../lib/copy";
import { JobDetailActions } from "./job-detail-actions";
import { JobDetailGuestGate } from "./job-detail-guest-gate";

/** Desktop/mobile aside CTA — company about card removed. */
export function JobDetailCompanySidebar({
  locale,
  model,
  onRevealForm,
  formOpen,
  preview,
}) {
  const t = text(locale);
  const showGate = model.authState === "guest";

  return (
    <div className="jd-cta-card">
      {showGate ? (
        <JobDetailGuestGate locale={locale} returnTo={model.returnTo} />
      ) : (
        <>
          <h2 className="jd-cta-title">{t.jdInterested}</h2>
          <p className="jd-cta-body">{t.jdInterestedBody}</p>
          <JobDetailActions
            locale={locale}
            model={model}
            layout="sidebar"
            onRevealForm={onRevealForm}
            formOpen={formOpen}
            preview={preview}
          />
        </>
      )}
    </div>
  );
}
