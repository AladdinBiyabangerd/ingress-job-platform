"use client";

import { JobDetailActions } from "./job-detail-actions";

export function JobDetailMobileSticky({
  locale,
  model,
  onRevealForm,
  onRevealAnalyze,
  onRevealApplyDraft,
  onRevealTailoredCv,
  formOpen,
  analyzeOpen,
  applyDraftOpen,
  tailoredCvOpen,
  preview,
}) {
  return (
    <div className="jd-sticky" data-preview={preview ? "1" : undefined}>
      <JobDetailActions
        locale={locale}
        model={model}
        layout="sticky"
        onRevealForm={onRevealForm}
        onRevealAnalyze={onRevealAnalyze}
        onRevealApplyDraft={onRevealApplyDraft}
        onRevealTailoredCv={onRevealTailoredCv}
        formOpen={formOpen}
        analyzeOpen={analyzeOpen}
        applyDraftOpen={applyDraftOpen}
        tailoredCvOpen={tailoredCvOpen}
        preview={preview}
      />
    </div>
  );
}
