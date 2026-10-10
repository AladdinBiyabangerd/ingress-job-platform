"use client";

import { JobDetailActions } from "./job-detail-actions";

export function JobDetailMobileSticky({
  locale,
  model,
  onRevealForm,
  onRevealAnalyze,
  formOpen,
  analyzeOpen,
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
        formOpen={formOpen}
        analyzeOpen={analyzeOpen}
        preview={preview}
      />
    </div>
  );
}
