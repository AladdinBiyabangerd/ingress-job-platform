import { loginHref } from "../../lib/auth-link";
import { text } from "../../lib/copy";
import { JdIcon } from "./jd-icons";

export function JobDetailGuestGate({ locale, returnTo, className = "" }) {
  const t = text(locale);
  const href = loginHref({ intent: "job_candidate", returnTo });

  return (
    <aside className={`jd-guest-gate ${className}`.trim()} aria-label={t.jdGuestGateTitle}>
      <div className="jd-guest-gate-icon" aria-hidden="true">
        <JdIcon name="lock" size={22} />
      </div>
      <div className="jd-guest-gate-body">
        <p className="jd-guest-gate-title">{t.jdGuestGateTitle}</p>
        <p className="jd-guest-gate-text">{t.jdGuestGateBody}</p>
        <a className="jd-guest-gate-link" href={href}>
          {t.jdGoAcademy}
        </a>
      </div>
    </aside>
  );
}
