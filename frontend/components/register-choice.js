"use client";

import { useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { employerPostingEnabled } from "../lib/product-features";
import { LoginLink } from "./login-link";

export function RegisterChoice({ locale, returnTo }) {
  const t = text(locale);
  const [open, setOpen] = useState(false);
  const back = returnTo || hrefFor(locale);
  const postingOn = employerPostingEnabled();
  if (!postingOn) {
    return (
      <div className="register-choice">
        <LoginLink className="account-link" intent="job_candidate" returnTo={back}>
          {t.register}
        </LoginLink>
      </div>
    );
  }
  return (
    <div className="register-choice">
      <button type="button" className="account-link" onClick={() => setOpen((value) => !value)}>
        {t.register}
      </button>
      {open ? (
        <div className="register-menu" role="group" aria-label={t.registerAsk}>
          <p>{t.registerAsk}</p>
          <LoginLink intent="job_employer" returnTo={hrefFor(locale, { mode: "company" })}>
            {t.registerPoster}
          </LoginLink>
          <LoginLink intent="job_candidate" returnTo={back}>
            {t.registerCreator}
          </LoginLink>
        </div>
      ) : null}
    </div>
  );
}
