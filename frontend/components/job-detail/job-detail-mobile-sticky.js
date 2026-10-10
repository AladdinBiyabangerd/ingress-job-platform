"use client";

import { JobDetailActions } from "./job-detail-actions";

export function JobDetailMobileSticky({
  locale,
  model,
  onRevealForm,
  onRevealAnalyze,
  onRevealApplyDraft,
  formOpen,
  analyzeOpen,
  applyDraftOpen,
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
        formOpen={formOpen}
        analyzeOpen={analyzeOpen}
        applyDraftOpen={applyDraftOpen}
        preview={preview}
      />
    </div>
  );
}
