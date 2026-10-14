import { useEffect, useState } from "react";
import { browseHrefFromPersist } from "../../lib/board-persist";
import { boardReturnHref, readBoardReturn } from "../../lib/board-return";
import { hrefFor, text } from "../../lib/copy";
import { JobDetailActions } from "./job-detail-actions";
import { JobDetailMeta } from "./job-detail-meta";
import { JdIcon } from "./jd-icons";

export function JobDetailHeader({
  locale,
  model,
  viewed = false,
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
  const t = text(locale);
  const company = model.company || {};
  const boardHref = hrefFor(locale) || "/";
  const [backHref, setBackHref] = useState(boardHref);
  useEffect(() => {
    const persisted = browseHrefFromPersist(locale);
    setBackHref(boardReturnHref(readBoardReturn(), persisted || boardHref));
  }, [boardHref, locale]);
  const external = model.listingType === "external";
  const opensLabel =
    model.hasOriginal && typeof model.originalOpens === "number"
      ? model.originalOpens > 0
        ? t.originalOpensCount?.(model.originalOpens)
        : t.originalOpensNone
      : null;
  const appsLabel =
    !opensLabel && typeof model.applications === "number"
      ? model.applications > 0
        ? t.applicationsCount?.(model.applications)
        : t.applicationsNone
      : null;
  const interestLabel = opensLabel || appsLabel;

  return (
    <header className={`jd-header${viewed ? " is-viewed" : ""}`}>
      <a className="jd-back" href={backHref}>
        <JdIcon name="back" size={16} />
        <span>{t.back}</span>
      </a>

      <div className="jd-header-top">
        <div className="jd-header-main">
          <div className="jd-company-row">
            <span className="jd-avatar jd-avatar-sm" aria-hidden="true">
              {company.initial}
            </span>
            <span className="jd-company-name">{company.name}</span>
            {external ? <span className="jd-external-badge">{t.jdExternal}</span> : null}
            {viewed ? <span className="jd-viewed-badge">{t.viewedJobBadge}</span> : null}
            {company.pageHref ? (
              <a className="jd-company-page-link" href={company.pageHref}>
                {t.jdCompanyPage}
                <JdIcon name="external" size={13} />
              </a>
            ) : null}
          </div>

          <h1 className="jd-title">{model.title}</h1>
          {model.intro ? <p className="jd-intro">{model.intro}</p> : null}
          {interestLabel ? <p className="jd-interest-count">{interestLabel}</p> : null}
        </div>
      </div>

      <JobDetailMeta meta={model.meta} />

      <div className="jd-header-actions">
        <JobDetailActions
          locale={locale}
          model={model}
          layout="desktop"
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

      <div className="jd-header-mobile-actions">
        <JobDetailActions
          locale={locale}
          model={model}
          layout="mobile"
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
    </header>
  );
}
