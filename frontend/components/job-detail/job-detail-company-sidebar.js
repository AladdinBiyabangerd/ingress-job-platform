import { text } from "../../lib/copy";
import { JobDetailActions } from "./job-detail-actions";
import { JobDetailGuestGate } from "./job-detail-guest-gate";
import { JdIcon } from "./jd-icons";

function Cover({ kind, name }) {
  const tone = kind === "laptop" ? "laptop" : "office";
  return (
    <div className={`jd-company-cover jd-company-cover-${tone}`} role="img" aria-label={name}>
      <span className="jd-company-cover-label">{name}</span>
    </div>
  );
}

export function JobDetailCompanySidebar({
  locale,
  model,
  onRevealForm,
  formOpen,
  preview,
}) {
  const t = text(locale);
  const company = model.company || {};
  const showGate = model.authState === "guest";
  const showFacts = company.size || company.industry || company.location;

  return (
    <aside className="jd-sidebar">
      <div className="jd-company-card">
        {company.cover ? <Cover kind={company.cover} name={company.name} /> : null}
        <div className="jd-company-card-body">
          <div className="jd-company-card-head">
            <span className="jd-avatar" aria-hidden="true">
              {company.initial}
            </span>
            <div>
              <h2 className="jd-company-card-title">
                {typeof t.jdAboutCompany === "function" ? t.jdAboutCompany(company.name) : company.name}
              </h2>
            </div>
          </div>
          {company.about ? <p className="jd-company-about">{company.about}</p> : null}
          {company.pageHref ? (
            <a className="jd-company-link" href={company.pageHref}>
              {t.jdVisitCompany}
              <JdIcon name="external" size={14} />
            </a>
          ) : null}
          {showFacts ? (
            <ul className="jd-company-facts">
              {company.size ? (
                <li>
                  <JdIcon name="users" size={16} />
                  <span>
                    <strong>{t.jdCompanySize}</strong>
                    <span>{company.size}</span>
                  </span>
                </li>
              ) : null}
              {company.industry ? (
                <li>
                  <JdIcon name="building" size={16} />
                  <span>
                    <strong>{t.jdIndustry}</strong>
                    <span>{company.industry}</span>
                  </span>
                </li>
              ) : null}
              {company.location ? (
                <li>
                  <JdIcon name="pin" size={16} />
                  <span>
                    <strong>{t.factLocation || "Location"}</strong>
                    <span>{company.location}</span>
                  </span>
                </li>
              ) : null}
            </ul>
          ) : null}
        </div>
      </div>

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
    </aside>
  );
}
