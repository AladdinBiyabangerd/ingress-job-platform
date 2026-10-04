"use client";

import { useState } from "react";
import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";

export function RegisterChoice({ locale, returnTo }) {
  const t = text(locale);
  const [open, setOpen] = useState(false);
  const back = returnTo || hrefFor(locale);
  return (
    <div className="register-choice">
      <button type="button" className="account-link" onClick={() => setOpen((value) => !value)}>
        {t.register}
      </button>
      {open ? (
        <div className="register-menu" role="group" aria-label={t.registerAsk}>
          <p>{t.registerAsk}</p>
          <a href={loginHref({ intent: "job_employer", returnTo: hrefFor(locale, { mode: "post" }) })}>
            {t.registerPoster}
          </a>
          <a href={loginHref({ intent: "job_candidate", returnTo: back })}>
            {t.registerCreator}
          </a>
        </div>
      ) : null}
    </div>
  );
}
