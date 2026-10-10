"use client";

import { JobDetailActions } from "./job-detail-actions";

export function JobDetailMobileSticky({ locale, model, onRevealForm, formOpen, preview }) {
  return (
    <div className="jd-sticky" data-preview={preview ? "1" : undefined}>
      <JobDetailActions
        locale={locale}
        model={model}
        layout="sticky"
        onRevealForm={onRevealForm}
        formOpen={formOpen}
        preview={preview}
      />
    </div>
  );
}
