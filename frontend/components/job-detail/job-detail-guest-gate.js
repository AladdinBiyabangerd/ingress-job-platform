import { text } from "../../lib/copy";
import { LoginLink } from "../login-link";
import { JdIcon } from "./jd-icons";

export function JobDetailGuestGate({ locale, returnTo, className = "" }) {
  const t = text(locale);

  return (
    <aside className={`jd-guest-gate ${className}`.trim()} aria-label={t.jdGuestGateTitle}>
      <div className="jd-guest-gate-icon" aria-hidden="true">
        <JdIcon name="lock" size={22} />
      </div>
      <div className="jd-guest-gate-body">
        <p className="jd-guest-gate-title">{t.jdGuestGateTitle}</p>
        <p className="jd-guest-gate-text">{t.jdGuestGateBody}</p>
        <LoginLink className="jd-guest-gate-link" intent="job_candidate" returnTo={returnTo}>
          {t.jdGoAcademy}
        </LoginLink>
      </div>
    </aside>
  );
}
