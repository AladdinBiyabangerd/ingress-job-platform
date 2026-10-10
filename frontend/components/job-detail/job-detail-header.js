import { hrefFor, text } from "../../lib/copy";
import { JobDetailActions } from "./job-detail-actions";
import { JobDetailMeta } from "./job-detail-meta";
import { JdIcon } from "./jd-icons";

export function JobDetailHeader({
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
  const t = text(locale);
  const company = model.company || {};
  const backHref = preview ? hrefFor(locale) : hrefFor(locale);
  const external = model.listingType === "external";

  return (
    <header className="jd-header">
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
            {company.pageHref ? (
              <a className="jd-company-page-link" href={company.pageHref}>
                {t.jdCompanyPage}
                <JdIcon name="external" size={13} />
              </a>
            ) : null}
          </div>

          <h1 className="jd-title">{model.title}</h1>
          {model.intro ? <p className="jd-intro">{model.intro}</p> : null}
        </div>

        <div className="jd-header-actions">
          <JobDetailActions
            locale={locale}
            model={model}
            layout="desktop"
            onRevealForm={onRevealForm}
            onRevealAnalyze={onRevealAnalyze}
            onRevealApplyDraft={onRevealApplyDraft}
            formOpen={formOpen}
            analyzeOpen={analyzeOpen}
            applyDraftOpen={applyDraftOpen}
            preview={preview}
          />
        </div>
      </div>

      <div className="jd-header-mobile-actions">
        <JobDetailActions
          locale={locale}
          model={model}
          layout="mobile"
          onRevealForm={onRevealForm}
          onRevealAnalyze={onRevealAnalyze}
          onRevealApplyDraft={onRevealApplyDraft}
          formOpen={formOpen}
          analyzeOpen={analyzeOpen}
          applyDraftOpen={applyDraftOpen}
          preview={preview}
        />
      </div>

      <JobDetailMeta meta={model.meta} />
    </header>
  );
}
